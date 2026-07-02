# LANDSCAPE

Related and competing tools in the "capture cameras / microphones /
screens on any OS from Python" space, benchmarked against
`capture-helper`. Ratings are `⭐️` (1) to `⭐️⭐️⭐️⭐️⭐️` (5), scored on
`capture-helper`'s intended job — a **library-shaped**, **OBS-inspired
without a GUI**, **AI-pipeline-first** capture layer that composes
with the rest of the AI Helpers stack (`video-helper`,
`podcast-helper`). A project optimised for a very different job
(e.g. full desktop live-streaming app) is not penalised — the score
just reflects fit to *this* niche.

## At a glance

| Library / project | Cross-platform enumeration (camera + mic) | Camera capture as `(H, W, 3)` numpy | Mic capture as float32 PCM frames | ffmpeg-native (no C extension of its own) | Live streaming / RTMP output | AI-pipeline ergonomics (`dict` returns, path-based API, drop-in for `video-helper` / `podcast-helper`) | Headless / no-GUI |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **capture-helper** *(this project)* | ⭐️⭐️⭐️⭐️⭐️ (avfoundation / v4l2 / dshow / pulse) | ⭐️⭐️⭐️⭐️⭐️ (`iter_camera_frames`) | ⭐️⭐️⭐️⭐️⭐️ (`iter_mic_audio`, async, Silero-VAD-shaped) | ⭐️⭐️⭐️⭐️⭐️ (pure subprocess) | ⭐️⭐️ (roadmap v0.4.0 — RTMP / HLS / Icecast) | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ |
| OpenCV `cv2.VideoCapture` | ⭐️⭐️ (no enumeration API; index-based) | ⭐️⭐️⭐️⭐️⭐️ (native BGR ndarray) | ⭐️ (video only) | ⭐️⭐️ (own C++ backend) | ⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ |
| PyAV | ⭐️⭐️⭐️ (avdevice bindings, but rough per-OS) | ⭐️⭐️⭐️⭐️ (frame → ndarray) | ⭐️⭐️⭐️ (audio frames) | ⭐️⭐️⭐️⭐️ (libav binding) | ⭐️⭐️⭐️ (writer API) | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ |
| sounddevice / soundcard | ⭐️⭐️⭐️⭐️ (audio only) | ⭐️ | ⭐️⭐️⭐️⭐️⭐️ (portaudio, callback-based) | ⭐️ (portaudio) | ⭐️ | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ |
| pyaudio | ⭐️⭐️⭐️ (audio only) | ⭐️ | ⭐️⭐️⭐️⭐️ (portaudio, blocking) | ⭐️ (portaudio) | ⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ |
| mss / pyautogui / pillow ImageGrab | ⭐️⭐️ (screen only, per-OS shim) | ⭐️⭐️⭐️⭐️ (RGB ndarray) | ⭐️ | ⭐️ | ⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ |
| OBS Studio (obs-websocket + obsws-python) | ⭐️⭐️⭐️⭐️ (via OBS scenes) | ⭐️⭐️ (through OBS pipeline, not native ndarray) | ⭐️⭐️ (through OBS pipeline) | ⭐️⭐️⭐️ (OBS' own capture) | ⭐️⭐️⭐️⭐️⭐️ (full RTMP / HLS / recording) | ⭐️⭐️ | ⭐️ (needs OBS running) |
| FFmpeg CLI (raw) | ⭐️⭐️⭐️⭐️⭐️ (`-list_devices`) | ⭐️⭐️ (roll your own reshape) | ⭐️⭐️ (roll your own reshape) | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️ (no Python types) | ⭐️⭐️⭐️⭐️⭐️ |
| GStreamer + PyGObject | ⭐️⭐️⭐️⭐️ (Linux-first) | ⭐️⭐️⭐️ (through appsink) | ⭐️⭐️⭐️ (through appsink) | ⭐️⭐️ (GStreamer plugins) | ⭐️⭐️⭐️⭐️⭐️ (rtmpsink / hlssink) | ⭐️⭐️ | ⭐️⭐️⭐️⭐️ |

## Positioning

`capture-helper` deliberately sits at the intersection of **OpenCV /
PyAV ergonomics for cameras** (numpy BGR frames) and **sounddevice
ergonomics for microphones** (float32 PCM frames), while keeping the
capture backend **entirely ffmpeg-driven** — no C extension of our
own, no portaudio dependency, no OBS process to keep alive. The
device catalog and the input arg builder are cross-platform in one
codebase, so higher-level tools (VAD, ASR, on-device ML) can consume
a live camera or mic through the **same iterator shape as the file-
based** `video_helper.extract_frames` / `podcast_helper.extract_audio_stream`.
That is the main differentiator against every alternative in the
table above.

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
- **mss / ImageGrab** — screenshots only, no camera or audio.
- **OBS Studio + obs-websocket** — you already run OBS and want to
  script scene switches, not consume raw frames in Python.
- **FFmpeg CLI (raw)** — you want zero Python dependency and are
  willing to write the reshape / plumbing yourself.
- **GStreamer + PyGObject** — Linux-first low-latency pipelines with
  RTMP / HLS out of the box; heavier to install, less portable.
