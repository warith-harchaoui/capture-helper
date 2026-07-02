# Capture Helper

[🇫🇷](LISEZMOI.md) · [🇬🇧](README.md)

[![CI](https://github.com/warith-harchaoui/capture-helper/actions/workflows/ci.yml/badge.svg)](https://github.com/warith-harchaoui/capture-helper/actions/workflows/ci.yml) [![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#)

`Capture Helper` belongs to a collection of libraries called `AI Helpers` developed for building Artificial Intelligence.

**OBS-inspired** (no GUI) capture + processing + publishing layer for the AI Helpers stack. Library-shaped: cross-platform camera / microphone / screen / window / application-audio sources, composable filter chains, multi-source mixing, and emit-to-publish primitives for live YouTube / Twitch RTMP, HLS, and Icecast — designed to plug into [video-helper](https://github.com/warith-harchaoui/video-helper) and [podcast-helper](https://github.com/warith-harchaoui/podcast-helper) for downstream frame / PCM contracts.

[🌍 AI Helpers](https://harchaoui.org/warith/ai-helpers)

[![logo](assets/logo.png)](https://harchaoui.org/warith/ai-helpers)

## Status — v0.1.0 INPUT layer

What ships today:

- `SourceKind` literal (`"camera"` | `"microphone"`)
- `Source` typed dict (kind, name, index, platform, driver)
- `MicFrame` typed dict (mirrors [`podcast_helper.PcmFrame`](https://github.com/warith-harchaoui/podcast-helper))
- `list_sources(kind=None)` — cross-platform device enumeration via `ffmpeg -list_devices` (macOS avfoundation / Windows dshow / Linux v4l2 + pulse)
- `pick_source(kind, *, name_substring=..., index=...)` — pick the first matching device, raises `ValueError` if nothing matches
- `iter_camera_frames(source, *, width=..., height=..., output_width=..., output_height=..., fps=..., max_frames=...)` — yields **`(H, W, 3)` BGR uint8 numpy arrays**, same contract as `video_helper.extract_frames`
- `iter_mic_audio(source, *, target_sample_rate=16000, to_mono=True, frame_ms=20)` — async iterator yielding `MicFrame`s, same contract as `podcast_helper.extract_audio_stream`
- `ffmpeg_input_args(source)` — exposed low-level helper for users wiring their own ffmpeg pipelines

```python
import asyncio
import capture_helper as ch

# Enumerate available devices
for s in ch.list_sources():
    print(f"{s['kind']:10s} [{s['index']}] {s['name']:40s} (driver={s['driver']})")
    # camera     [0] FaceTime HD Camera                       (driver=avfoundation)
    # microphone [0] Built-in Microphone                      (driver=avfoundation)

# Camera → numpy BGR frames (drop-in for video_helper.extract_frames)
cam = ch.pick_source("camera")
for frame in ch.iter_camera_frames(cam, output_width=640, output_height=360,
                                   fps=30, max_frames=300):
    # frame.shape == (360, 640, 3), dtype uint8, BGR.
    do_something(frame)

# Microphone → async PCM stream (drop-in for podcast_helper.extract_audio_stream)
async def listen():
    mic = ch.pick_source("microphone")
    async for f in ch.iter_mic_audio(mic, target_sample_rate=16000,
                                     to_mono=True, frame_ms=20):
        # f["pcm"].shape == (320,) — 20ms @ 16kHz mono.
        await asr.feed(f["pcm"])
asyncio.run(listen())
```

## Roadmap

| Version | Layer | Scope |
|---|---|---|
| v0.0.1 | INPUT scaffold | `list_sources` + types |
| **v0.1.0** (this release) | INPUT | `pick_source(...)` + `iter_camera_frames(source, ...)` + `iter_mic_audio(source, ...)` — composes with video-helper / podcast-helper contracts |
| **v0.2.0** | INPUT extended | Screen / window capture; basic filter chain (noise gate, gain, scale) |
| **v0.3.0** | PROCESS | Scenes / mixer — `mix_audio([sources], levels=[...])` + `compose_video([sources], layout=...)` |
| **v0.4.0** | PUBLISH | `emit_to_youtube_live(...)`, `emit_to_twitch_live(...)`, `emit_to_rtmp(...)`, `emit_to_hls(...)`, `emit_audio_to_icecast(...)` |
| **v0.5.0** | OUTPUT virtual | `output_to_virtual_camera(...)` (pyvirtualcam etc.), `output_to_virtual_mic(...)` |
| **v0.6.0** | OBS integration | OBS WebSocket client (react to scene / stream events) |

For a full cookbook (per-OS ffmpeg input strings, snapshot capture, live preview, ASR / VAD wiring), see [📋 EXAMPLES.md](EXAMPLES.md).

## Multi-surface exposure

`capture-helper` ships the same INPUT layer through **five surfaces**
so it plugs in wherever you already work — no rewrite needed.

| Surface | Install | Entry point | Use case |
| --- | --- | --- | --- |
| **Python library** | `pip install …@v0.2.0` | `import capture_helper as ch` | Notebooks, scripts, other AI Helpers |
| **argparse CLI** | *(no extra)* | `capture-helper …` | Shells, cron, CI, container CMD |
| **click CLI** | `[cli]` extra | `capture-helper-click …` | Users on a click-native stack (completion, colored `--help`) |
| **FastAPI HTTP** | `[api]` extra | `uvicorn capture_helper.api:app` | Reverse-proxied service, JSON / multipart clients |
| **MCP tools** | `[api,mcp]` extras | `capture-helper-mcp` | LLM agents (Claude Desktop, custom MCP clients) |

```bash
# CLI (argparse — always available)
capture-helper list-sources
capture-helper pick-source --kind camera --name FaceTime
capture-helper capture-mic --output mic.wav --seconds 3

# CLI (click twin — same subcommands)
capture-helper-click list-sources
capture-helper-click capture-camera --output-dir frames/ \
    --output-width 640 --output-height 360 --max-frames 30

# HTTP surface
uvicorn capture_helper.api:app --host 0.0.0.0 --port 8000
curl http://localhost:8000/sources
curl -o frames.zip \
    'http://localhost:8000/capture/camera?output_width=320&output_height=240&max_frames=10'

# MCP surface (FastAPI + fastapi-mcp)
capture-helper-mcp   # serves HTTP routes + MCP endpoint on :8000

# Docker (ships FastAPI + MCP by default)
docker build -t capture-helper .
docker run --rm -p 8000:8000 capture-helper
```

For a GUI vision (device wall + PGM/PVW cueing, not a CLI mirror),
see [📋 GUI.md](GUI.md). For a competitive comparison against
OpenCV / PyAV / sounddevice / OBS / FFmpeg CLI / GStreamer, see
[📋 LANDSCAPE.md](LANDSCAPE.md).

## Installation

```bash
pip install --force-reinstall --no-cache-dir \
  git+https://github.com/warith-harchaoui/capture-helper.git@v0.2.0
```

Optional extras (pick what you need):

```bash
pip install 'capture-helper[cli] @ git+…@v0.2.0'         # click CLI
pip install 'capture-helper[api] @ git+…@v0.2.0'         # FastAPI HTTP
pip install 'capture-helper[api,mcp] @ git+…@v0.2.0'     # MCP tools
```

You still need `ffmpeg` on PATH for device enumeration and live capture to return anything:

- macOS 🍎 : `brew install ffmpeg`

  (install `brew` thanks to [brew.sh](https://brew.sh/))
- Ubuntu 🐧 : `sudo apt install ffmpeg`
- Windows 🪟 : grab a build from [ffmpeg.org/download.html](https://ffmpeg.org/download.html) and add it to `PATH`.

# Author
 - [Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui)

# Acknowledgements
Special thanks to [Mohamed Chelali](https://mchelali.github.io) and [Bachir Zerroug](https://www.linkedin.com/in/bachirzerroug) for fruitful discussions.
