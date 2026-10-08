# CMK Voice Cloning API — container image for RunPod GPU pods.
#
# Build:   docker build -t cmk-voice .
# RunPod:  point a GPU pod at this image, expose 8000, and mount a
#          network volume on /workspace so saved voices survive restarts.

FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

# System tools: ffmpeg for any audio wrangling the API might need.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Python deps first (better layer caching when only code changes).
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# The application itself.
COPY server.py ./

# Where voice samples live. Mount persistent storage here on RunPod,
# otherwise uploaded voices vanish when the pod stops.
VOLUME ["/workspace/voices"]

# Sensible defaults; override per deployment with pod env vars.
ENV CMK_VOX_MODEL=openbmb/VoxCPM-0.5B \
    CMK_VOICE_HOME=/workspace/voices \
    CMK_GEN_TIMEOUT=900 \
    CMK_USE_DENOISER=0 \
    PORT=8000

EXPOSE 8000

# Keep connections alive a while: generations can run for minutes.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "300"]
