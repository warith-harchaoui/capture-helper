# Landscape

[🇫🇷 PAYSAGE.md](https://github.com/warith-harchaoui/capture-helper/blob/main/PAYSAGE.md) · 🇬🇧 English

Related and competing tools in the "capture cameras / microphones /
screens on any OS from Python" space, benchmarked against
`capture-helper`. Ratings run ⭐ (1) to ⭐⭐⭐⭐⭐ (5), scored against
`capture-helper`'s intended job: a **library-shaped**,
**AI-pipeline-first** capture layer with a **browser scene
configurator**, composing with the rest of the AI Helpers stack
(`video-helper`, `podcast-helper`). A project optimised for a very
different job (a full desktop live-streaming app, say) is not
penalised; the score just reflects fit to *this* niche.

## At a glance

<!-- TABLE:START -->
| Live Capture | Cross-platform enumeration | Camera as numpy | Mic as PCM frames | ffmpeg-native | Live streaming | AI-pipeline ergonomics | Headless |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **capture-helper** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| OpenCV | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| PyAV | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| sounddevice | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| PyAudio | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| mss | ⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| VidGear | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| OBS Studio | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ |
| FFmpeg CLI | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| GStreamer | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
<!-- TABLE:END -->

## Positioning map

<!-- FIGURE:START -->
2D representation of the table above.

![Positioning map](https://raw.githubusercontent.com/warith-harchaoui/capture-helper/main/assets/landscape.png)

The map is a 2-D summary of the seven criteria, so read it as a shape, not a scoreboard. `capture-helper` is at the top-right corner. The axes read **Horizontal: Adaptable ↔ Versatile** and **Vertical: Accessible ↔ Intuitive**.
<!-- FIGURE:END -->

## Positioning

`capture-helper` deliberately sits at the intersection of **OpenCV /
PyAV ergonomics for cameras** (numpy BGR frames) and **sounddevice
ergonomics for microphones** (float32 PCM frames), while keeping the
capture backend **entirely ffmpeg-driven**: no C extension of our
own, no portaudio dependency, no separate desktop app to keep alive. The
device catalog and the input arg builder are cross-platform in one
codebase, so higher-level tools (VAD, ASR, on-device ML) can consume
a live camera or mic through the **same iterator shape as the file-
based** `video_helper.extract_frames` / `podcast_helper.extract_audio_stream`.
That is the main differentiator against every alternative in the
table above.

Each alternative carries nuance the stars compress. OpenCV's
`cv2.VideoCapture` has no enumeration API (you address cameras by
bare index) but hands back a native BGR ndarray. PyAV exposes
`avdevice` bindings that reach every backend at the cost of rough,
per-OS setup. sounddevice and pyaudio are portaudio-backed and
audio-only, callback- and blocking-based respectively. mss (with
pyautogui / Pillow `ImageGrab`) grabs the screen as an RGB ndarray but
sees no camera or microphone. VidGear wraps OpenCV for camera frames and
layers FFmpeg-backed streaming (`WriteGear` / `StreamGear`) on top, so it
captures and streams video well but exposes no microphone path. OBS
Studio shines at full RTMP / HLS / recording and can be scripted through
its WebSocket API, but it needs the desktop app alive and does not hand
you raw frames. The raw FFmpeg CLI enumerates with `-list_devices` and
streams anywhere, yet leaves the reshape and Python typing to you.
GStreamer with PyGObject is a Linux-first, low-latency pipeline with
`rtmpsink` / `hlssink` out of the box, heavier to install and less
portable.

## When to pick what

- **`capture-helper`**: headless Python-first capture for AI
  pipelines, cross-platform enumeration plus numpy BGR frames plus
  async PCM frames, composing with the rest of the AI Helpers suite.
- **OpenCV `cv2.VideoCapture`**: you already have OpenCV and only
  need cameras, no mics, no cross-OS enumeration niceties.
- **PyAV**: you want direct libav access and are comfortable
  wrestling with `avdevice` per-OS.
- **sounddevice**: mic-only, portaudio-backed callback reads,
  no video.
- **PyAudio**: mic-only, blocking portaudio reads, no video.
- **mss**: screenshots only, no camera or audio.
- **VidGear**: you want a high-performance OpenCV-backed video
  framework with built-in FFmpeg streaming; cameras only, no
  microphone path.
- **OBS Studio**: you already run the full desktop streaming app
  and want to script scene switches through its WebSocket API, not
  consume raw frames in Python.
- **FFmpeg CLI (raw)**: you want zero Python dependency and are
  willing to write the reshape / plumbing yourself.
- **GStreamer + PyGObject**: Linux-first low-latency pipelines with
  RTMP / HLS out of the box, heavier to install, less portable.

## Sources and as-of date

The stars are a judgement of **fit to this niche**, not a benchmark: nothing
here was timed, and no throughput figure is claimed. What was checked is the
*capability* behind each column — which project enumerates devices, which hands
back a numpy array, which has a microphone path at all — against each project's
own documentation, on **2026-10-27**. Capture APIs move slowly, but one project
adding a microphone gear or an enumeration call would make a row of this table
wrong about someone else, so the date is part of the claim.

- [OpenCV `videoio` module](https://github.com/opencv/opencv/tree/4.x/modules/videoio) — the `VideoCapture` backends; cameras are addressed by bare index, with no enumeration entry point
- [PyAV documentation](https://pyav.org/docs/stable/) — the libav bindings, device input included
- [python-sounddevice documentation](https://python-sounddevice.readthedocs.io/) — PortAudio-backed, audio only, callback-oriented
- [PyAudio documentation](https://people.csail.mit.edu/hubert/pyaudio/docs/) — PortAudio-backed, audio only, blocking reads
- [python-mss documentation](https://python-mss.readthedocs.io/) — screen only; no camera, no audio
- [VidGear gears](https://abhitronix.github.io/vidgear/latest/gears/) — the full gear list, which is where "no microphone path" comes from
- [obs-websocket](https://github.com/obsproject/obs-websocket) — the scripting surface OBS Studio exposes, and what it does (and does not) hand back
- [FFmpeg device documentation](https://ffmpeg.org/ffmpeg-devices.html) — `avfoundation` / `dshow` / `v4l2` / `pulse` / `alsa`, and the `-list_devices` flag this package shells out to
- [GStreamer Python bindings](https://gstreamer.freedesktop.org/bindings/python.html) — PyGObject, the install this table calls heavier

`capture-helper`'s own row is not sourced from a document: it is read off the
code in this repository, at the version in `pyproject.toml`.
