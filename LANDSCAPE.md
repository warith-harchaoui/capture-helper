# Landscape

[🇫🇷 PAYSAGE.md](https://github.com/warith-harchaoui/capture-helper/blob/main/PAYSAGE.md) · 🇬🇧 English

Related and competing tools in the "capture cameras / microphones /
screens on any OS from Python" space, benchmarked against
`capture-helper`. Ratings are ⭐ (1) to ⭐⭐⭐⭐⭐ (5), scored on
`capture-helper`'s intended job — a **library-shaped**,
**AI-pipeline-first** capture layer with a **browser scene
configurator**, that composes with the rest of the AI Helpers stack
(`video-helper`, `podcast-helper`). A project optimised for a very
different job (e.g. a full desktop live-streaming app) is not
penalised — the score just reflects fit to *this* niche.

## At a glance

<!-- TABLE:START -->
| Live Capture | Cross-platform enumeration | Camera as numpy | Mic as PCM frames | ffmpeg-native | Live streaming | AI-pipeline ergonomics | Headless |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **capture-helper** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| OpenCV | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| PyAV | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| sounddevice | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| pyaudio | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| mss | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Desktop streaming GUIs | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ |
| FFmpeg CLI | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| GStreamer | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
<!-- TABLE:END -->

## Positioning map

<!-- FIGURE:START -->
2D representation of the table above.

![Positioning map](https://raw.githubusercontent.com/warith-harchaoui/capture-helper/main/assets/landscape.png)

The map is a 2-D summary of the seven criteria, so read it as a shape, not a scoreboard. `capture-helper` is at the top-right corner. The axes read **Horizontal — Visual ↔ Media** and **Vertical — Streaming ↔ Intuitive**.
<!-- FIGURE:END -->

## Positioning

`capture-helper` deliberately sits at the intersection of **OpenCV /
PyAV ergonomics for cameras** (numpy BGR frames) and **sounddevice
ergonomics for microphones** (float32 PCM frames), while keeping the
capture backend **entirely ffmpeg-driven** — no C extension of our
own, no portaudio dependency, no separate desktop app to keep alive. The
device catalog and the input arg builder are cross-platform in one
codebase, so higher-level tools (VAD, ASR, on-device ML) can consume
a live camera or mic through the **same iterator shape as the file-
based** `video_helper.extract_frames` / `podcast_helper.extract_audio_stream`.
That is the main differentiator against every alternative in the
table above.

Each alternative carries nuance the stars compress. OpenCV's
`cv2.VideoCapture` has no enumeration API — you address cameras by
bare index — but hands back a native BGR ndarray. PyAV exposes
`avdevice` bindings that reach every backend at the cost of rough,
per-OS setup. sounddevice and pyaudio are portaudio-backed and
audio-only, callback- and blocking-based respectively. mss (with
pyautogui / Pillow `ImageGrab`) grabs the screen as an RGB ndarray but
sees no camera or microphone. Desktop streaming GUIs shine at full
RTMP / HLS / recording and can be scripted through a WebSocket API, but
they need the desktop app alive and do not hand you raw frames. The raw
FFmpeg CLI enumerates with `-list_devices` and streams anywhere, yet
leaves the reshape and Python typing to you. GStreamer with PyGObject
is a Linux-first, low-latency pipeline with `rtmpsink` / `hlssink` out
of the box, heavier to install and less portable.

## When to pick what

- **`capture-helper`** — headless Python-first capture for AI
  pipelines, cross-platform enumeration + numpy BGR frames + async
  PCM frames, composes with the rest of the AI Helpers suite.
- **OpenCV `cv2.VideoCapture`** — you already have OpenCV and only
  need cameras, no mics, no cross-OS enumeration niceties.
- **PyAV** — you want direct libav access and are comfortable
  wrestling with `avdevice` per-OS.
- **sounddevice / soundcard** — mic-only, portaudio is acceptable,
  no video.
- **pyaudio** — mic-only, blocking portaudio reads, no video.
- **mss / ImageGrab** — screenshots only, no camera or audio.
- **Desktop streaming GUIs** — you already run a full desktop
  streaming app and want to script scene switches through its
  WebSocket API, not consume raw frames in Python.
- **FFmpeg CLI (raw)** — you want zero Python dependency and are
  willing to write the reshape / plumbing yourself.
- **GStreamer + PyGObject** — Linux-first low-latency pipelines with
  RTMP / HLS out of the box; heavier to install, less portable.
