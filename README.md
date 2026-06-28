# Capture Helper

`Capture Helper` belongs to a collection of libraries called `AI Helpers` developed for building Artificial Intelligence.

**OBS-inspired** (no GUI) capture + processing + publishing layer for the AI Helpers stack. Library-shaped: cross-platform camera / microphone / screen / window / application-audio sources, composable filter chains, multi-source mixing, and emit-to-publish primitives for live YouTube / Twitch RTMP, HLS, and Icecast — designed to plug into [video-helper](https://github.com/warith-harchaoui/video-helper) and [podcast-helper](https://github.com/warith-harchaoui/podcast-helper) for downstream frame / PCM contracts.

[🕸️ AI Helpers](https://harchaoui.org/warith/ai-helpers)

[![logo](assets/logo.png)](https://harchaoui.org/warith/ai-helpers)

## Status — v0.0.1 scaffold

This release is **a scaffold**. It exposes the public types and basic device enumeration. The heavy lifting (per-source iteration, filter chains, mixer, publish layer) lands in subsequent releases.

What works today:

- `SourceKind` literal (`"camera"` | `"microphone"`)
- `Source` typed dict (kind, name, index, platform, driver)
- `list_sources(kind=None)` — cross-platform device enumeration via `ffmpeg -list_devices` (macOS avfoundation / Windows dshow / Linux v4l2 + pulse)

```python
from capture_helper import list_sources

for s in list_sources("microphone"):
    print(f"[{s['index']}] {s['name']} (driver={s['driver']})")
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

## Installation

```bash
pip install --force-reinstall --no-cache-dir \
  git+https://github.com/warith-harchaoui/capture-helper.git@v0.0.1
```

You need `ffmpeg` on PATH for device enumeration to return anything:

- macOS 🍎 : `brew install ffmpeg`
- Ubuntu 🐧 : `sudo apt install ffmpeg`
- Windows 🪟 : grab a build from [ffmpeg.org/download.html](https://ffmpeg.org/download.html) and add it to `PATH`.

# Author
 - [Warith HARCHAOUI](https://harchaoui.org/warith)

# Acknowledgements
Special thanks to [Mohamed Chelali](https://mchelali.github.io) and [Bachir Zerroug](https://www.linkedin.com/in/bachirzerroug) for fruitful discussions.
