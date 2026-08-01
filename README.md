# Capture Helper

[🇫🇷](https://github.com/warith-harchaoui/capture-helper/blob/main/LISEZMOI.md) · [🇬🇧](https://github.com/warith-harchaoui/capture-helper/blob/main/README.md)

[![CI](https://github.com/warith-harchaoui/capture-helper/actions/workflows/ci.yml/badge.svg)](https://github.com/warith-harchaoui/capture-helper/actions/workflows/ci.yml) [![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://github.com/warith-harchaoui/capture-helper/blob/main/LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#) [![Local-first](https://img.shields.io/badge/privacy-local--first-2f6f5e.svg)](#the-promise)

`Capture Helper` belongs to a collection of libraries called `AI Helpers` developed for building Artificial Intelligence.

Local-first, **library-shaped camera / microphone capture layer** for the AI Helpers stack, with a **live multi-source scene configurator** GUI. It turns your live cameras and microphones into the same array / PCM contracts the rest of the suite consumes — `iter_camera_frames` yields `(H, W, 3)` BGR uint8 arrays like [video-helper](https://github.com/warith-harchaoui/video-helper)'s `extract_frames`, and `iter_mic_audio` yields `MicFrame`s like [podcast-helper](https://github.com/warith-harchaoui/podcast-helper)'s `extract_audio_stream` — and lets you compose several live sources on a canvas, preview them in the browser, and save the design as a reusable JSON scene the CLI / API can replay. Early-stage: the capture iterators are stable; the scene configurator is new.

[🌍 AI Helpers](https://harchaoui.org/warith/ai-helpers)

[![logo](https://raw.githubusercontent.com/warith-harchaoui/capture-helper/main/assets/logo.png)](https://harchaoui.org/warith/ai-helpers)

## The Promise

**Local-first by design.** capture-helper runs entirely on your machine; camera and microphone data is captured and processed locally — never uploaded to any third-party service, no telemetry, no account, no cloud lock-in. Part of the [AI Helpers](https://github.com/warith-harchaoui/ai-helpers) suite: sovereignty over your data through local-first Open Source.

## Documentation

[💻 Documentation](https://harchaoui.org/warith/ai-helpers/docs/capture-helper-doc/)

[🗺️ Landscape](https://github.com/warith-harchaoui/capture-helper/blob/main/LANDSCAPE.md)

[📋 Examples](https://github.com/warith-harchaoui/capture-helper/blob/main/EXAMPLES.md)

## Features

Early-stage, but here is exactly what exists today.

**Capture layer (stable contracts)**

- `SourceKind` literal (`"camera"` | `"microphone"`)
- `Source` typed dict (kind, name, index, platform, driver)
- `MicFrame` typed dict (mirrors [`podcast_helper.PcmFrame`](https://github.com/warith-harchaoui/podcast-helper))
- `list_sources(kind=None)` — cross-platform device enumeration via `ffmpeg -list_devices` (macOS avfoundation / Windows dshow / Linux v4l2 + pulse)
- `pick_source(kind, *, name_substring=..., index=...)` — pick the first matching device, raises `ValueError` if nothing matches
- `iter_camera_frames(source, *, width=..., height=..., output_width=..., output_height=..., fps=..., max_frames=...)` — yields **`(H, W, 3)` BGR uint8 numpy arrays**, same contract as `video_helper.extract_frames`
- `iter_mic_audio(source, *, target_sample_rate=16000, to_mono=True, frame_ms=20)` — async iterator yielding `MicFrame`s, same contract as `podcast_helper.extract_audio_stream`
- `ffmpeg_input_args(source)` — exposed low-level helper for users wiring their own ffmpeg pipelines

**Live multi-source scene configurator (new, additive)**

- **Browser GUI at `GET /gui`** — enumerate all cameras + microphones, drop them onto a 16:9 canvas, **live-preview each camera** as an in-browser MJPEG stream, watch **live microphone level meters**, drag / arrange the tiles, then **save the visual design as a reusable JSON scene** (and load one back). No build step: vanilla JS + Tailwind CDN.
- **Scene model** — `Scene` / `SceneSource` typed dicts, `new_scene(...)`, `add_source(...)`, `validate_scene(...)`, `save_scene(...)`, `load_scene(...)`, `resolve_scene_sources(...)` (map a scene onto the current machine's devices), `scene_from_available_devices(...)`.
- **Live-preview primitives** — `snapshot_jpeg(source)` (one live JPEG), `iter_camera_jpeg(source)` (JPEG stream for MJPEG), `mic_level(source)` (RMS / peak dBFS for a VU meter), `frame_to_jpeg(frame)`.
- **Scene CLI** — `capture-helper scene-auto` (auto-populate from devices), `scene-validate`, `scene-show` (report how each source resolves here).
- **Scene / preview HTTP endpoints** — `GET /scene`, `POST /scene/save`, `POST /scene/load`, `GET /preview/camera.jpg`, `GET /preview/camera.mjpeg`, `GET /preview/mic-level`.

The scene configurator is a **live multi-source scene configurator**: a visual layout of live cameras / microphones that serialises to a portable artifact — the design becomes a headless, scriptable capture recipe.

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
| **v0.1.0** | INPUT | `pick_source(...)` + `iter_camera_frames(source, ...)` + `iter_mic_audio(source, ...)` — composes with video-helper / podcast-helper contracts |
| **v0.3.0** (this release) | SCENES + GUI | Scene model (save / load / validate / resolve), live-preview primitives (camera JPEG / MJPEG, mic level), and the browser-based live multi-source scene configurator at `/gui` |
| **next** | INPUT extended | Screen / window capture; basic filter chain (noise gate, gain, scale) |
| **later** | PROCESS | Multi-source mixer — `mix_audio([sources], levels=[...])` + `compose_video([sources], layout=...)` running a saved scene into a single output |

For a full cookbook (per-OS ffmpeg input strings, snapshot capture, live preview, scene save/load, ASR / VAD wiring), see [📋 EXAMPLES.md](https://github.com/warith-harchaoui/capture-helper/blob/main/EXAMPLES.md). For the exhaustive trigger catalogue, see [📋 TRIGGERS.md](https://github.com/warith-harchaoui/capture-helper/blob/main/TRIGGERS.md).

## Multi-surface exposure

`capture-helper` ships the same capabilities through **five surfaces**
so it plugs in wherever you already work — no rewrite needed.

| Surface | Install | Entry point | Use case |
| --- | --- | --- | --- |
| **Python library** | `pip install capture-helper` | `import capture_helper as ch` | Notebooks, scripts, other AI Helpers |
| **argparse CLI** | *(no extra)* | `capture-helper …` | Shells, cron, CI, container CMD |
| **click CLI** | `[cli]` extra | `capture-helper-click …` | Users on a click-native stack (completion, colored `--help`) |
| **FastAPI HTTP** | `[api]` extra | `uvicorn capture_helper.api:app` | Reverse-proxied service, JSON / multipart clients |
| **Browser GUI** | `[api]` extra | `GET /gui` | Live multi-source scene configurator (preview + arrange + save) |

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

# Browser GUI — live multi-source scene configurator
uvicorn capture_helper.api:app --port 8000
# open http://localhost:8000/gui  (or just http://localhost:8000/)

# Docker (ships FastAPI + GUI by default)
docker build -t capture-helper .
docker run --rm -p 8000:8000 capture-helper
```

The **GUI** at `/gui` is the live multi-source scene configurator: it enumerates your cameras / microphones, live-previews each camera (MJPEG) and each mic (level meter), lets you arrange them on a canvas, and saves the design as a reusable `.scene.json` the CLI / API can replay. See [📋 GUI.md](https://github.com/warith-harchaoui/capture-helper/blob/main/GUI.md).

## Installation

**Prerequisites** — **Python 3.10–3.13** and **git**, **ffmpeg**, **PortAudio**, cross-platform:

- 🍎 **macOS** ([Homebrew](https://brew.sh)): `brew install python git ffmpeg portaudio`
- 🐧 **Ubuntu/Debian**: `sudo apt update && sudo apt install -y python3 python3-pip git ffmpeg portaudio19-dev`
- 🪟 **Windows** (PowerShell): `winget install Python.Python.3.12 Git.Git Gyan.FFmpeg` (PortAudio ships inside the Python wheels)

We recommend using Python environments. Check this link if you're unfamiliar with setting one up: [🥸 Tech tips](https://harchaoui.org/warith/4ml/#install).

You still need `ffmpeg` on PATH for device enumeration and live capture to return anything.

### From PyPI (recommended)

```bash
# Core INPUT layer (list/pick sources, camera + mic iterators)
pip install capture-helper

# Optional surfaces
pip install "capture-helper[cli]"       # click-based CLI twin
pip install "capture-helper[api]"       # FastAPI HTTP surface
```

### From source (no PyPI)

```bash
# Core INPUT layer
pip install "git+https://github.com/warith-harchaoui/capture-helper.git@v0.3.0"

# Optional surfaces
pip install "capture-helper[cli] @ git+https://github.com/warith-harchaoui/capture-helper.git@v0.3.0"
pip install "capture-helper[api] @ git+https://github.com/warith-harchaoui/capture-helper.git@v0.3.0"
```

## Author

 - [Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui)

## Acknowledgements

Special thanks to [Mohamed Chelali](https://mchelali.github.io) and [Bachir Zerroug](https://www.linkedin.com/in/bachirzerroug) for fruitful discussions.

## License

This project is licensed under the BSD-3-Clause License — see the [LICENSE](LICENSE) file for details.
