# Capture Helper

[🇫🇷](LISEZMOI.md) · [🇬🇧](README.md)

[![CI](https://github.com/warith-harchaoui/capture-helper/actions/workflows/ci.yml/badge.svg)](https://github.com/warith-harchaoui/capture-helper/actions/workflows/ci.yml) [![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#)

`Capture Helper` belongs to a collection of libraries called `AI Helpers` developed for building Artificial Intelligence.

**OBS-inspired** (no GUI) capture + processing + publishing layer for the AI Helpers stack. Library-shaped: cross-platform camera / microphone / screen / window / application-audio sources, composable filter chains, multi-source mixing, and emit-to-publish primitives for live YouTube / Twitch RTMP, HLS, and Icecast — designed to plug into [video-helper](https://github.com/warith-harchaoui/video-helper) and [podcast-helper](https://github.com/warith-harchaoui/podcast-helper) for downstream frame / PCM contracts.

[🌍 AI Helpers](https://harchaoui.org/warith/ai-helpers)

[![logo](assets/logo.png)](https://harchaoui.org/warith/ai-helpers)

## Status — v0.0.1 scaffold

This release is **a scaffold**. It exposes the public types and basic device enumeration. The heavy lifting (per-source iteration, filter chains, mixer, publish layer) lands in subsequent releases.

What works today:

- `SourceKind` literal (`"camera"` | `"microphone"`)
- `Source` typed dict (kind, name, index, platform, driver)
- `list_sources(kind=None)` — cross-platform device enumeration via `ffmpeg -list_devices` (macOS avfoundation / Windows dshow / Linux v4l2 + pulse)

```python
import capture_helper as ch

for s in ch.list_sources():
    print(f"{s['kind']:10s} [{s['index']}] {s['name']:40s} (driver={s['driver']})")
    # camera     [0] FaceTime HD Camera                       (driver=avfoundation)
    # camera     [1] iPhone Camera                            (driver=avfoundation)
    # microphone [0] Built-in Microphone                      (driver=avfoundation)
    # microphone [1] BlackHole 16ch                           (driver=avfoundation)
```

## Roadmap

| Version | Layer | Scope |
|---|---|---|
| **v0.0.1** (this release) | INPUT scaffold | `list_sources` + types |
| **v0.1.0** | INPUT | `pick_source(...)` + `iter_camera_frames(source, ...)` + `iter_mic_audio(source, ...)` — composes with video-helper / podcast-helper contracts |
| **v0.2.0** | INPUT extended | Screen / window capture; basic filter chain (noise gate, gain, scale) |
| **v0.3.0** | PROCESS | Scenes / mixer — `mix_audio([sources], levels=[...])` + `compose_video([sources], layout=...)` |
| **v0.4.0** | PUBLISH | `emit_to_youtube_live(...)`, `emit_to_twitch_live(...)`, `emit_to_rtmp(...)`, `emit_to_hls(...)`, `emit_audio_to_icecast(...)` |
| **v0.5.0** | OUTPUT virtual | `output_to_virtual_camera(...)` (pyvirtualcam etc.), `output_to_virtual_mic(...)` |
| **v0.6.0** | OBS integration | OBS WebSocket client (react to scene / stream events) |

For a full cookbook (per-OS ffmpeg input string, snapshot capture, v0.1.0 design preview, roadmap), see [📋 EXAMPLES.md](EXAMPLES.md).

## Installation

```bash
pip install --force-reinstall --no-cache-dir \
  git+https://github.com/warith-harchaoui/capture-helper.git@v0.0.1
```

You need `ffmpeg` on PATH for device enumeration to return anything:

- macOS 🍎 : `brew install ffmpeg`

  (install `brew` thanks to [brew.sh](https://brew.sh/))
- Ubuntu 🐧 : `sudo apt install ffmpeg`
- Windows 🪟 : grab a build from [ffmpeg.org/download.html](https://ffmpeg.org/download.html) and add it to `PATH`.

# Author
 - [Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui)

# Acknowledgements
Special thanks to [Mohamed Chelali](https://mchelali.github.io) and [Bachir Zerroug](https://www.linkedin.com/in/bachirzerroug) for fruitful discussions.
