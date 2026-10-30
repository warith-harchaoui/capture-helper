# Capture Helper

[🇫🇷](https://github.com/warith-harchaoui/capture-helper/blob/main/LISEZMOI.md) · [🇬🇧](https://github.com/warith-harchaoui/capture-helper/blob/main/README.md)

[![CI](https://github.com/warith-harchaoui/capture-helper/actions/workflows/ci.yml/badge.svg)](https://github.com/warith-harchaoui/capture-helper/actions/workflows/ci.yml) [![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://github.com/warith-harchaoui/capture-helper/blob/main/LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#) [![Local-first](https://img.shields.io/badge/privacy-local--first-2f6f5e.svg)](#the-promise)

`Capture Helper` belongs to a collection of libraries called `AI Helpers` developed for building Artificial Intelligence.

Local-first library that turns a live camera or microphone into data the rest of the AI Helpers suite already knows how to consume, plus a browser GUI for arranging several such sources at once.

The two iterators are the whole idea. Each emits exactly what its sibling package emits from a recorded file:

| Live source | Iterator | What it yields | Identical to |
|---|---|---|---|
| Camera | `iter_camera_frames` | one array per frame: a grid of pixel colours, height × width × three channels stored blue, green, red — the `BGR uint8` format OpenCV and this suite use | [video-helper](https://github.com/warith-harchaoui/video-helper)'s `extract_frames` |
| Microphone | `iter_mic_audio` | `MicFrame` chunks: small blocks of raw audio measurements taken over time, in the standard pulse-code modulation (PCM) format | [podcast-helper](https://github.com/warith-harchaoui/podcast-helper)'s `extract_audio_stream` |

That table is the payoff: because both iterators speak the shapes their siblings speak, code written against a recorded video file or a downloaded podcast runs unchanged against a live camera or microphone.

The GUI sits on top. Drag several live sources onto a canvas, preview them in the browser, then save the layout as a reusable JSON scene the CLI or the API can replay later. The two iterators are the stable foundation; the scene configurator, added more recently, builds on them.

[🌍 AI Helpers](https://deraison.ai/ai-helpers)

[![logo](https://raw.githubusercontent.com/warith-harchaoui/capture-helper/main/assets/logo.png)](https://deraison.ai/ai-helpers)

## The Promise

**Local-first by design.** capture-helper runs entirely on your machine; camera and microphone data is captured and processed locally, never uploaded to any third-party service, with no telemetry, no account, no cloud lock-in. Part of the [AI Helpers](https://github.com/warith-harchaoui/ai-helpers) suite: sovereignty over your data through local-first Open Source.

**Battle-tested, not a prototype.** Every change goes through the same gate before it ships: the full test suite and a lint pass run in continuous integration (see the CI badge above). Only a green run gets tagged and published to PyPI under semantic versioning. Downstream, [vocal-helper](https://github.com/warith-harchaoui/vocal-helper) depends on capture-helper's live microphone path to feed its speech pipeline in production, so the camera and microphone iterators carry real workloads, not just their own tests.

## Documentation

[💻 Documentation](https://deraison.ai/ai-helpers/docs/capture-helper-doc/)

[🗺️ Landscape](https://github.com/warith-harchaoui/capture-helper/blob/main/LANDSCAPE.md)

[📋 Examples](https://github.com/warith-harchaoui/capture-helper/blob/main/EXAMPLES.md)

## Features

Here is exactly what exists today.

**Capture layer (stable contracts)**

- `SourceKind` literal (`"camera"` | `"microphone"`)
- `Source` typed dict (kind, name, index, platform, driver)
- `MicFrame` typed dict, mirroring [`podcast_helper.PcmFrame`](https://github.com/warith-harchaoui/podcast-helper)
- `list_sources(kind=None)`: cross-platform device enumeration via `ffmpeg -list_devices` (macOS avfoundation, Windows dshow, Linux v4l2 + pulse)
- `pick_source(kind, *, name_substring=..., index=...)`: picks the first matching device, raises `ValueError` if nothing matches
- `iter_camera_frames(source, *, width=..., height=..., output_width=..., output_height=..., fps=..., max_frames=...)`: yields **`(H, W, 3)` BGR uint8 numpy arrays**, the same contract as `video_helper.extract_frames`
- `iter_mic_audio(source, *, target_sample_rate=16000, to_mono=True, frame_ms=20)`: async iterator yielding `MicFrame`s, the same contract as `podcast_helper.extract_audio_stream`
- `ffmpeg_input_args(source)`: a low-level helper exposed for users wiring their own ffmpeg pipelines

**Live multi-source scene configurator (new, additive)**

- **Browser GUI at `GET /gui`**: enumerate all cameras and microphones, drop them onto a 16:9 canvas, **live-preview each camera** as an in-browser MJPEG stream, watch **live microphone level meters**, drag them into place, then **save the visual design as a reusable JSON scene** (and load one back). No build step: vanilla JS + Tailwind CDN.
- **Scene model**: `Scene` / `SceneSource` typed dicts, `new_scene(...)`, `add_source(...)`, `validate_scene(...)`, `save_scene(...)`, `load_scene(...)`, `resolve_scene_sources(...)` (maps a scene onto the current machine's devices), `scene_from_available_devices(...)`.
- **Live-preview primitives**: `snapshot_jpeg(source)` (one live JPEG), `iter_camera_jpeg(source)` (JPEG stream for MJPEG), `mic_level(source)` (RMS / peak dBFS for a VU meter), `frame_to_jpeg(frame)`.
- **Scene CLI**: `capture-helper scene-auto` (auto-populate from devices), `scene-validate`, `scene-show` (reports how each source resolves here).
- **Scene / preview HTTP endpoints**: `GET /scene`, `POST /scene/save`, `POST /scene/load`, `GET /preview/camera.jpg`, `GET /preview/camera.mjpeg`, `GET /preview/mic-level`.

What makes this more than a live-preview widget is that the layout itself becomes data: arranging cameras and microphones on the canvas produces a portable JSON file, so the same scene can be replayed later, on a different machine, from the command line, with no browser involved.

```python
import asyncio
import capture_helper as ch

# Enumerate available devices
for s in ch.list_sources():
    print(f"{s['kind']:10s} [{s['index']}] {s['name']:40s} (driver={s['driver']})")
    # camera     [0] FaceTime HD Camera                       (driver=avfoundation)
    # microphone [1] MacBook Pro Microphone                   (driver=avfoundation)

# Camera → numpy BGR frames (drop-in for video_helper.extract_frames)
cam = ch.pick_source("camera")
for frame in ch.iter_camera_frames(
    cam, output_width=640, output_height=360, fps=30, max_frames=300
):
    # frame.shape == (360, 640, 3), dtype uint8, BGR.
    do_something(frame)


# Microphone → async PCM stream (drop-in for podcast_helper.extract_audio_stream)
async def listen():
    mic = ch.pick_source("microphone")
    async for f in ch.iter_mic_audio(mic, target_sample_rate=16000, to_mono=True, frame_ms=20):
        # f["pcm"].shape == (320,), 20ms of audio at 16kHz mono.
        await asr.feed(f["pcm"])


asyncio.run(listen())
```

## How it works

![How capture-helper works: the camera and the microphone, behind the same contract as the rest of the suite](https://raw.githubusercontent.com/warith-harchaoui/capture-helper/main/assets/diagrams/how-it-works.png)

## Installation

**Prerequisites**: **Python 3.10-3.13**, **git** and **ffmpeg**, cross-platform:

- 🍎 **macOS** ([Homebrew](https://brew.sh)): `brew install python git ffmpeg`
- 🐧 **Ubuntu/Debian**: `sudo apt update && sudo apt install -y python3 python3-pip git ffmpeg`
- 🪟 **Windows** (PowerShell): `winget install Python.Python.3.12 Git.Git Gyan.FFmpeg`

We recommend using Python environments. Check this link if you're unfamiliar with setting one up: [🥸 Tech tips](https://deraison.ai/4ml/#install).

You still need `ffmpeg` on PATH for device enumeration and live capture to return anything.

### From PyPI (recommended)

```bash
# Core INPUT layer (list/pick sources, camera + mic iterators)
pip install capture-helper

# Optional surfaces
pip install "capture-helper[api]"       # FastAPI HTTP surface
```

### From source (no PyPI)

```bash
git clone https://github.com/warith-harchaoui/capture-helper.git
cd capture-helper
pip install -e .

# Optional surfaces
pip install -e ".[api]"
```

## Quick start

The shortest useful path: find a device, read frames off it. No scene file, no
browser, no extra install. `list_sources` only shells out to
`ffmpeg -list_devices`, so it is safe to call on a machine with nothing plugged
in — it returns `[]` instead of raising.

```python
import capture_helper as ch

for s in ch.list_sources():
    print(f"{s['kind']:10s} [{s['index']}] {s['name']:40s} (driver={s['driver']})")
# camera     [0] FaceTime HD Camera                       (driver=avfoundation)
# microphone [1] MacBook Pro Microphone                   (driver=avfoundation)
# (abridged: the machine this was run on also lists two Continuity devices
#  and a virtual audio input)

cam = ch.pick_source("camera", name_substring="FaceTime")
for frame in ch.iter_camera_frames(cam, output_width=224, output_height=224, fps=30, max_frames=2):
    print(frame.shape, frame.dtype)
# (224, 224, 3) uint8
# (224, 224, 3) uint8
```

The same two steps from the shell:

```bash
capture-helper list-sources
capture-helper capture-camera --output-dir frames/ \
    --output-width 480 --output-height 270 --fps 30 --max-frames 3
# frames/frame_000000.bgr24
# frames/frame_000001.bgr24
# frames/frame_000002.bgr24
```

**Pass `fps`.** On macOS the `avfoundation` driver blocks instead of failing
when the frame rate is left unset, or set to a value the device does not
actually offer, so a camera call without `fps=` can hang indefinitely rather
than raise. `## Troubleshooting` in
[EXAMPLES.md](https://github.com/warith-harchaoui/capture-helper/blob/main/EXAMPLES.md)
has the details, including how to list the modes a device accepts.

## Roadmap

| Version | Layer | Scope |
|---|---|---|
| v0.0.1 | INPUT scaffold | `list_sources` + types |
| v0.1.0 | INPUT | `pick_source(...)`, `iter_camera_frames(source, ...)`, `iter_mic_audio(source, ...)`; composes with the video-helper / podcast-helper contracts |
| v0.3.0 | SCENES + GUI | Scene model (save / load / validate / resolve), live-preview primitives (camera JPEG / MJPEG, mic level), and the browser-based live multi-source scene configurator at `/gui` |
| v1.0.0 | Contracts frozen | The iterator contracts stop being provisional; CI becomes a blocking gate rather than a report |
| v1.1.0 | MCP | The FastAPI app re-exposed as MCP tools (`capture-helper-mcp`, `[mcp]` extra) |
| **v1.6.0** (current) | One door per surface | A single `click` command line replaces the argparse / click pair, and the GUI's strings move to a `gettext` catalogue |
| **next** | INPUT extended | Screen / window capture; basic filter chain (noise gate, gain, scale) |
| **later** | PROCESS | Multi-source mixer: `mix_audio([sources], levels=[...])` + `compose_video([sources], layout=...)`, running a saved scene into a single output |

For a full cookbook (per-OS ffmpeg input strings, snapshot capture, live preview, scene save/load, ASR / VAD wiring), see [📋 EXAMPLES.md](https://github.com/warith-harchaoui/capture-helper/blob/main/EXAMPLES.md). For the exhaustive trigger catalogue, see [📋 TRIGGERS.md](https://github.com/warith-harchaoui/capture-helper/blob/main/TRIGGERS.md).

## Multi-surface exposure

`capture-helper` ships the same capabilities through **five surfaces**, so it plugs in wherever you already work with no rewrite needed.

| Surface | Install | Entry point | Use case |
| --- | --- | --- | --- |
| **Python library** | `pip install capture-helper` | `import capture_helper as ch` | Notebooks, scripts, other AI Helpers |
| **CLI** | *(no extra)* | `capture-helper …` | Shells, cron, CI, container CMD |
| **FastAPI HTTP** | `[api]` extra | `uvicorn capture_helper.api:app` | Reverse-proxied service, JSON / multipart clients |
| **Browser GUI** | `[api]` extra | `GET /gui` | Live multi-source scene configurator (preview + arrange + save) |
| **MCP** | `[mcp]` extra | `capture-helper-mcp` | Any MCP-aware agent host (same FastAPI app, `/mcp` endpoint) |

```bash
# CLI
capture-helper list-sources
capture-helper pick-source --kind camera --name FaceTime
capture-helper capture-mic --output mic.wav --seconds 3
capture-helper stream-mic | my-live-consumer   # raw f32le PCM, unbounded
capture-helper capture-camera --output-dir frames/ \
    --output-width 640 --output-height 360 --fps 30 --max-frames 30

# HTTP surface
uvicorn capture_helper.api:app --host 0.0.0.0 --port 8000
curl http://localhost:8000/sources
curl -o frames.zip \
    'http://localhost:8000/capture/camera?output_width=320&output_height=240&max_frames=10'

# Browser GUI: live multi-source scene configurator
uvicorn capture_helper.api:app --port 8000
# open http://localhost:8000/gui  (or just http://localhost:8000/)

# Docker (ships FastAPI + GUI by default)
docker build -t capture-helper .
docker run --rm -p 8000:8000 capture-helper

# Same thing through Compose, with the port, env and health probe already set
docker compose up --build
```

The **GUI** at `/gui` is the live multi-source scene configurator: it enumerates your cameras and microphones, live-previews each camera (MJPEG) and each mic (level meter), lets you arrange them on a canvas, and saves the design as a reusable `.scene.json` the CLI / API can replay. See [📋 GUI.md](https://github.com/warith-harchaoui/capture-helper/blob/main/GUI.md).

The page speaks **French and English**. `GET /gui?lang=fr|en` picks one, a flag
in the header toggles between them, and a code the locale file does not carry
falls back to the default rather than failing. Every string lives in
[`capture_helper/locales/fr/LC_MESSAGES/capture_helper.po`](https://github.com/warith-harchaoui/capture-helper/blob/main/capture_helper/locales/fr/LC_MESSAGES/capture_helper.po),
a standard `gettext` catalogue read through `os_helper.Catalog` — the loader
shared across the suite — so
translating the page never means opening a Python file.

### Use it as an agent skill

`skills/capture-helper/` packages capture-helper as a **Claude Skill** *and* an **OpenCode
skill**, so an agent can reach for it on your behalf. See
[`skills/README.md`](https://github.com/warith-harchaoui/capture-helper/blob/main/skills/README.md) to install it (symlink into
`~/.claude/skills/` and `~/.opencode/skills/`), and
[`TRIGGERS.md`](https://github.com/warith-harchaoui/capture-helper/blob/main/TRIGGERS.md) for the exhaustive trigger catalogue —
`scripts/check_triggers.py` keeps the skill's description in sync with it, and
the test suite fails if a capability stops being named.

## Rust rewrite

A companion crate, [`capture-helper-rs`](https://github.com/warith-harchaoui/capture-helper-rs),
rewrites the microphone half — device enumeration plus a streaming `MicFrame`
iterator on top of [`cpal`](https://crates.io/crates/cpal) — in native Rust.
No camera, no GUI, no video, just the audio-capture core. The interest: it
talks to CoreAudio/WASAPI/ALSA-PulseAudio-JACK-PipeWire directly, so it needs
neither `ffmpeg` nor a Python runtime on the target machine — a better fit
when live mic capture is embedded inside a Rust application (a native app, an
embedded device) rather than orchestrated from Python.

## Author

 - [Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui)

## Acknowledgements

Special thanks to [Mohamed Chelali](https://mchelali.github.io) and [Bachir Zerroug](https://www.linkedin.com/in/bachirzerroug) for fruitful discussions.

## License

This project is licensed under the BSD-3-Clause License; see the [LICENSE](https://github.com/warith-harchaoui/capture-helper/blob/main/LICENSE) file for details.
