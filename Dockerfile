# syntax=docker/dockerfile:1.6
#
# capture-helper — reproducible container image.
#
# One-stage build: pulls system deps (ffmpeg is mandatory — the INPUT
# layer shells out to it for enumeration and live capture; PulseAudio
# is included for the Linux microphone path) and installs the package
# with the [api,mcp] extras so the container serves the HTTP + MCP
# surfaces out of the box.
#
# Build:
#   docker build -t capture-helper .
#
# Run (HTTP + MCP on 0.0.0.0:8000):
#   docker run --rm -p 8000:8000 capture-helper
#
# Run CLI one-shot:
#   docker run --rm -v $PWD:/data capture-helper \
#     capture-helper list-sources
#
# Note: real camera / microphone capture inside the container needs
# host-device passthrough (``--device /dev/video0`` on Linux) and is
# out of scope for the default image — enumeration alone works headless.

FROM python:3.11-slim AS base

# System deps: ffmpeg for every capture pipeline, libsndfile in case
# downstream code loads audio, tini for signal handling. No compilers
# — we install from wheels only.
RUN apt-get update && apt-get install --no-install-recommends -y \
        ffmpeg \
        libsndfile1 \
        pulseaudio-utils \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Non-root runtime user; the app never needs root at runtime.
RUN useradd --create-home --shell /bin/bash app
WORKDIR /app

# Copy the package first so pip picks up pyproject.toml before we
# invalidate the layer with source changes.
COPY --chown=app:app pyproject.toml README.md LICENSE ./
COPY --chown=app:app capture_helper ./capture_helper

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir '.[api,mcp]'

USER app
EXPOSE 8000
ENV PYTHONUNBUFFERED=1 \
    CAPTURE_HELPER_HOST=0.0.0.0 \
    CAPTURE_HELPER_PORT=8000

# tini reaps orphan children (ffmpeg subprocesses) cleanly on SIGTERM.
ENTRYPOINT ["/usr/bin/tini", "--"]
# Default: serve FastAPI + MCP. Override for one-shot CLI usage.
CMD ["capture-helper-mcp"]
