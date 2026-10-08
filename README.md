# CMK Voice Cloning API

A self-hosted voice cloning service. Upload a short voice sample once, then
turn any text — including Myanmar (Burmese) — into speech in that voice.

Voice cloning API inspired by VoxCPM (openbmb). Original implementation.

---

## How it works

1. **Record** 10–30 seconds of clear speech (a phone recording is fine).
2. **Upload** it with the exact words you said — the transcript is what lets
   the model lock onto your voice.
3. **Speak** any text through the `/tts` endpoint using your `voice_id`.

The model (VoxCPM) downloads automatically from Hugging Face on first boot,
so there is nothing to fetch by hand.

## API quick reference

| Method | Path           | What it does                                              |
|--------|----------------|-----------------------------------------------------------|
| GET    | `/health`      | Is the model loaded? Which device? How many voices?       |
| GET    | `/voices`      | Voices saved on this server                               |
| POST   | `/upload-voice`| Form: `audio` file, `name`, `prompt_text` → `voice_id`    |
| POST   | `/tts`         | JSON: `text`, `voice_id` (+ optional `guide`, `steps`)    |
| POST   | `/clone`       | One-shot: `audio` + `text` → WAV, nothing stored          |
| POST   | `/style-voice` | JSON: `text`, `style` ("warm narrator") — no sample needed|

All audio in/out is 16 kHz mono WAV. Responses are the raw WAV bytes.

Example — register a voice with curl:

```bash
curl -X POST http://POD_IP:8000/upload-voice \
  -F "audio=@my-voice.wav" \
  -F "name=My Voice" \
  -F "prompt_text=the exact words spoken in the recording"
# -> {"voice_id": "a1b2c3d4e5f6", "label": "My Voice"}
```

Example — speak:

```bash
curl -X POST http://POD_IP:8000/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "မင်္ဂလာပါ", "voice_id": "a1b2c3d4e5f6"}' \
  --output out.wav
```

## Deploying on RunPod

1. **Account + funds** — sign up at runpod.io and add ~$10 of credit to try it.
2. **Get this code onto the pod.** Easiest: push these four files to a GitHub
   repo, then in RunPod choose *Pods → Deploy → Build from GitHub* and point
   it at the repo.
3. **Pick a GPU.** RTX 4090 (~$0.50/hr) is comfortable for the default
   0.5B model. The bigger VoxCPM 1.5/2 models need 16 GB+ VRAM.
4. **Expose port 8000** (TCP) so you can reach the API.
5. **Attach a network volume at `/workspace`.** Without this, uploaded voices
   disappear every time the pod restarts.
6. **Deploy and wait.** First boot downloads the model (~1.5 GB) and loads it —
   give it 5–10 minutes, then open `http://POD_IP:8000/health`.
   `"status": "ok"` means you are live.

### Switching models

Set the pod env var `CMK_VOX_MODEL`:

- `openbmb/VoxCPM-0.5B` — default, ~1.5 GB, runs on 8 GB VRAM
- `openbmb/VoxCPM1.5` — ~1.9 GB, better quality
- `openbmb/VoxCPM2` — ~4.6 GB, best quality, needs 16 GB+ VRAM

Other knobs: `CMK_GEN_TIMEOUT` (seconds, default 900),
`CMK_USE_DENOISER=1` to enable the denoiser, `PORT`.

## Tips for good clones

- Record in a quiet room, 10–30 seconds, natural speaking pace.
- The `prompt_text` must match the recording **word for word**.
- Myanmar text works — the splitter understands `။` as a sentence end.
- If output sounds rushed, lower `guide` (try 1.6); if it ignores the voice,
  raise it (try 2.6).

## Limits to know

- One generation at a time per pod (GPU work is serialized). Busy service?
  run a second pod.
- No streaming — each request returns the complete WAV.
- Burmese output quality should be spot-checked with real samples before
  depending on it for production narration.
