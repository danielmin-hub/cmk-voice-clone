"""
CMK Voice Cloning API
======================
A self-hosted voice cloning service built on VoxCPM (openbmb).

Voice cloning API inspired by VoxCPM (openbmb). Original implementation.

What it does:
    Register a short voice sample once, then turn any text into speech
    that sounds like that voice. Myanmar (Burmese) text is fully supported.

Endpoints:
    GET  /health        service + model status
    GET  /voices        voices registered on this server
    POST /upload-voice  save a voice sample, get back a voice_id
    POST /tts           speak text in a registered voice  -> WAV
    POST /clone         one-shot: sample + text in, WAV out (not saved)

Configuration (environment variables):
    CMK_VOX_MODEL       Hugging Face model id (default "openbmb/VoxCPM-0.5B")
    CMK_VOICE_HOME      where voice samples live (default "/workspace/voices")
    CMK_GEN_TIMEOUT     seconds before a generation is abandoned (default 900)
    CMK_USE_DENOISER    "1" to enable the denoiser, anything else skips it
    PORT                listen port (default 8000)
"""

from __future__ import annotations

import asyncio
import gc
import io
import json
import logging
import os
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf
import torch

# VoxCPM's dynamo hook can misbehave on some CUDA builds; switching it off
# keeps generation stable. This is a VoxCPM-specific quirk, not our logic.
try:  # pragma: no cover - depends on torch internals
    import torch._dynamo  # type: ignore

    torch._dynamo.config.disable = True
except Exception:
    pass

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

# ----------------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)
logger = logging.getLogger("cmk-voice")

MODEL_REF = os.environ.get("CMK_VOX_MODEL", "openbmb/VoxCPM-0.5B")
VOICE_HOME = Path(os.environ.get("CMK_VOICE_HOME", "/workspace/voices"))
CATALOG_PATH = VOICE_HOME / "catalog.json"
GEN_TIMEOUT = int(os.environ.get("CMK_GEN_TIMEOUT", "900"))
USE_DENOISER = os.environ.get("CMK_USE_DENOISER", "0") == "1"
PORT = int(os.environ.get("PORT", "8000"))

ON_GPU = torch.cuda.is_available()
RUNTIME = "cuda" if ON_GPU else "cpu"

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
PAUSE_BETWEEN_LINES = 0.15  # seconds of silence stitched between sentences


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ----------------------------------------------------------------------------
# The generation engine: wraps the VoxCPM model with our own chunking,
# loudness hygiene, and GPU housekeeping.
# ----------------------------------------------------------------------------

class SpeechEngine:
    """Loads VoxCPM once and turns text into waveforms, sentence by sentence."""

    def __init__(self, model_ref: str, use_denoiser: bool = False) -> None:
        self.model_ref = model_ref
        self.use_denoiser = use_denoiser
        self._vox = None
        self._gate = threading.Lock()  # CUDA inference must not overlap itself

    def boot(self) -> None:
        from voxcpm import VoxCPM  # imported late so --help stays fast

        logger.info("Booting VoxCPM from %s on %s", self.model_ref, RUNTIME)
        self._vox = VoxCPM.from_pretrained(self.model_ref, load_denoiser=self.use_denoiser)
        logger.info("VoxCPM ready (output rate %d Hz)", self.output_rate())

    def output_rate(self) -> int:
        try:
            return int(self._vox.tts_model.sample_rate)
        except Exception:
            return 16000

    @staticmethod
    def split_into_lines(text: str) -> List[str]:
        """Carve text into speakable lines at sentence boundaries.

        Handles both Latin punctuation and the Myanmar full stop (U+104B),
        so mixed-language scripts still chunk sensibly.
        """
        staged = text
        for mark in ("။", ".", "?", "!"):
            staged = staged.replace(mark, mark + "\n")
        lines = [ln.strip() for ln in staged.split("\n")]
        return [ln for ln in lines if len(ln) >= 2]

    def _one_line(self, line: str, sample_path: Optional[str], sample_script: Optional[str],
                  guide: float, steps: int) -> np.ndarray:
        args: Dict[str, Any] = {
            "text": line + " ",
            "cfg_value": guide,
            "inference_timesteps": steps,
        }
        if sample_path:
            args["prompt_wav_path"] = sample_path
        if sample_script:
            args["prompt_text"] = sample_script
        with self._gate:
            with torch.inference_mode():
                piece = self._vox.generate(**args)
        return np.asarray(piece, dtype=np.float32).reshape(-1)

    def render(self, text: str, sample_path: Optional[str] = None,
               sample_script: Optional[str] = None,
               guide: float = 2.1, steps: int = 15) -> Tuple[np.ndarray, int]:
        """Render full text -> (mono float32 waveform, sample rate)."""
        if self._vox is None:
            raise RuntimeError("Speech engine has not booted yet")

        lines = self.split_into_lines(text)
        if not lines:
            raise ValueError("Nothing speakable in the provided text")

        rate = self.output_rate()
        breather = np.zeros(int(rate * PAUSE_BETWEEN_LINES), dtype=np.float32)
        pieces: List[np.ndarray] = []

        try:
            for idx, line in enumerate(lines):
                pieces.append(self._one_line(line, sample_path, sample_script, guide, steps))
                if idx < len(lines) - 1:
                    pieces.append(breather)
                self._tidy_gpu()
        finally:
            self._tidy_gpu()

        track = np.concatenate(pieces) if pieces else np.zeros(0, dtype=np.float32)
        return track, rate

    @staticmethod
    def _tidy_gpu() -> None:
        gc.collect()
        if ON_GPU:
            torch.cuda.empty_cache()

    @staticmethod
    def pack_wav(track: np.ndarray, rate: int) -> bytes:
        """Encode a float32 mono track as 16-bit PCM WAV bytes."""
        sink = io.BytesIO()
        sf.write(sink, track, rate, format="WAV", subtype="PCM_16")
        return sink.getvalue()


# ----------------------------------------------------------------------------
# Voice library: on-disk catalog of user-uploaded voice samples.
# ----------------------------------------------------------------------------

class VoiceLibrary:
    """Keeps voice samples + their transcripts in a JSON catalog."""

    def __init__(self, home: Path, catalog: Path) -> None:
        self.home = home
        self.catalog = catalog

    def _read(self) -> Dict[str, Dict[str, Any]]:
        if not self.catalog.exists():
            return {}
        try:
            return json.loads(self.catalog.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Voice catalog unreadable (%s); starting empty", exc)
            return {}

    def _write(self, data: Dict[str, Dict[str, Any]]) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        self.catalog.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def add(self, raw_audio: bytes, label: str, transcript: str) -> Dict[str, str]:
        voice_id = uuid.uuid4().hex[:12]
        self.home.mkdir(parents=True, exist_ok=True)
        dest = self.home / f"{voice_id}.wav"
        dest.write_bytes(raw_audio)

        data = self._read()
        data[voice_id] = {
            "label": label,
            "transcript": transcript,
            "file": str(dest),
            "added": _now_iso(),
        }
        self._write(data)
        return {"voice_id": voice_id, "label": label}

    def get(self, voice_id: str) -> Optional[Dict[str, Any]]:
        return self._read().get(voice_id)

    def listing(self) -> List[Dict[str, str]]:
        return [
            {"voice_id": vid, "label": v.get("label", vid), "added": v.get("added", "")}
            for vid, v in self._read().items()
        ]


engine = SpeechEngine(MODEL_REF, use_denoiser=USE_DENOISER)
library = VoiceLibrary(VOICE_HOME, CATALOG_PATH)


# ----------------------------------------------------------------------------
# Request shapes
# ----------------------------------------------------------------------------

class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)
    voice_id: str = Field(..., min_length=1)
    guide: float = Field(2.1, ge=0.5, le=5.0)
    steps: int = Field(15, ge=4, le=50)


class StyleRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)
    style: str = Field(..., min_length=1, max_length=500)
    guide: float = Field(2.1, ge=0.5, le=5.0)
    steps: int = Field(15, ge=4, le=50)


# ----------------------------------------------------------------------------
# App wiring
# ----------------------------------------------------------------------------

@asynccontextmanager
async def service_life(app: FastAPI):
    VOICE_HOME.mkdir(parents=True, exist_ok=True)
    engine.boot()
    logger.info("CMK voice API online")
    yield
    logger.info("CMK voice API stopping")


app = FastAPI(title="CMK Voice Cloning API", version="1.0.0", lifespan=service_life)


async def _guarded(call, *args, **kwargs):
    """Run blocking GPU work off the event loop, with a hard timeout."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(call, *args, **kwargs), timeout=GEN_TIMEOUT
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Voice generation took too long")


def _check_audio_blob(blob: bytes) -> None:
    if not blob:
        raise HTTPException(status_code=400, detail="Uploaded audio is empty")
    if len(blob) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Audio exceeds the 50 MB limit")
    try:
        with io.BytesIO(blob) as stream:
            meta = sf.info(stream)
        logger.info("Sample accepted: %s, %.1fs at %d Hz", meta.format, meta.duration, meta.samplerate)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read audio file: {exc}")


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "model": MODEL_REF,
        "runtime": RUNTIME,
        "gpu": ON_GPU,
        "voices": len(library.listing()),
        "time": _now_iso(),
    }


@app.get("/voices")
async def voices():
    return {"voices": library.listing()}


@app.post("/upload-voice")
async def register_voice(
    audio: UploadFile = File(...),
    name: str = Form(...),
    prompt_text: str = Form(...),
):
    """Save a personal voice sample.

    Send a 10-30 second recording of clear speech plus the EXACT words
    spoken in it (prompt_text). The closer the transcript matches, the
    better the clone.
    """
    label = name.strip()
    script = prompt_text.strip()
    if not label:
        raise HTTPException(status_code=400, detail="A voice name is required")
    if not script:
        raise HTTPException(status_code=400, detail="The sample transcript is required")

    blob = await audio.read()
    _check_audio_blob(blob)
    saved = library.add(blob, label, script)
    logger.info("Registered voice '%s' as %s", label, saved["voice_id"])
    return saved


@app.post("/tts")
async def speak(req: SpeakRequest):
    """Speak text using a registered voice. Responds with WAV audio."""
    entry = library.get(req.voice_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Unknown voice_id")
    sample_file = entry.get("file", "")
    if not sample_file or not Path(sample_file).exists():
        raise HTTPException(status_code=410, detail="Voice sample file is gone")

    logger.info("Speaking %d chars with voice %s", len(req.text), req.voice_id)
    try:
        track, rate = await _guarded(
            engine.render,
            req.text,
            sample_path=sample_file,
            sample_script=entry.get("transcript"),
            guide=req.guide,
            steps=req.steps,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Speech render failed")
        raise HTTPException(status_code=500, detail=f"Could not render speech: {exc}")

    return Response(content=engine.pack_wav(track, rate), media_type="audio/wav")


@app.post("/clone")
async def instant_clone(
    audio: UploadFile = File(...),
    text: str = Form(...),
    prompt_text: str = Form(""),
    guide: float = Form(2.1),
    steps: int = Form(15),
):
    """Clone on the fly: voice sample + text in, WAV out. Nothing is stored."""
    words = text.strip()
    if not words:
        raise HTTPException(status_code=400, detail="Text is required")

    blob = await audio.read()
    _check_audio_blob(blob)

    scratch = VOICE_HOME / f".scratch_{uuid.uuid4().hex[:8]}.wav"
    try:
        VOICE_HOME.mkdir(parents=True, exist_ok=True)
        scratch.write_bytes(blob)
        logger.info("One-shot clone of %d chars", len(words))
        track, rate = await _guarded(
            engine.render,
            words,
            sample_path=str(scratch),
            sample_script=prompt_text.strip() or None,
            guide=guide,
            steps=steps,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("One-shot clone failed")
        raise HTTPException(status_code=500, detail=f"Could not render speech: {exc}")
    finally:
        try:
            scratch.unlink(missing_ok=True)
        except Exception:
            pass

    return Response(content=engine.pack_wav(track, rate), media_type="audio/wav")


@app.post("/style-voice")
async def style_voice(req: StyleRequest):
    """Describe a voice in words ("warm female narrator, slow") and speak text.

    No sample needed: the description is woven into the request so the
    model aims for that style.
    """
    direction = f"({req.style.strip()}) {req.text.strip()}"
    logger.info("Styled speech: '%s...', %d chars", req.style[:48], len(req.text))
    try:
        track, rate = await _guarded(
            engine.render, direction, guide=req.guide, steps=req.steps
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Styled speech failed")
        raise HTTPException(status_code=500, detail=f"Could not render speech: {exc}")

    return Response(content=engine.pack_wav(track, rate), media_type="audio/wav")


if __name__ == "__main__":  # local runs; RunPod uses the Dockerfile instead
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=PORT)
