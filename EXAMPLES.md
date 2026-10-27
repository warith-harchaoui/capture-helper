# Capture Helper Examples

[🇫🇷](https://github.com/warith-harchaoui/capture-helper/blob/main/EXEMPLES.md) · [🇬🇧](https://github.com/warith-harchaoui/capture-helper/blob/main/EXAMPLES.md)

Practical recipes for `capture-helper`: **cross-platform device enumeration,
selection and live iterators** for cameras and microphones, plus the scene
model and the live-preview primitives the browser configurator is built on.

The outputs pasted below were produced by running the snippets on a macOS
machine (`avfoundation`, a built-in FaceTime camera and a MacBook microphone).
Device names and JPEG byte counts belong to that machine and to what the camera
was pointed at; shapes, dtypes, sample counts and error messages do not. Where
a snippet could not be run offline — because it needs a sibling package, a
speech model or a browser — it says so instead of showing an output it never
produced.

---

## Table of Contents

- [Setup](#setup)
- [1. List and filter the available sources](#1-list-and-filter-the-available-sources)
- [2. Pick a specific device](#2-pick-a-specific-device)
- [3. Camera → numpy BGR frames](#3-camera--numpy-bgr-frames)
- [4. Microphone → async PCM stream](#4-microphone--async-pcm-stream)
- [5. Compose with the video-helper / podcast-helper contracts](#5-compose-with-the-video-helper--podcast-helper-contracts)
- [6. Build the per-OS ffmpeg input string yourself](#6-build-the-per-os-ffmpeg-input-string-yourself)
- [7. Inspect a `Source` typed dict](#7-inspect-a-source-typed-dict)
- [8. Design, save and replay a scene](#8-design-save-and-replay-a-scene)
- [9. Live preview (JPEG / MJPEG / mic level)](#9-live-preview-jpeg--mjpeg--mic-level)
- [10. The browser scene configurator (`/gui`)](#10-the-browser-scene-configurator-gui)
- [Command line](#command-line)
- [Troubleshooting](#troubleshooting)

---

## Setup

```bash
pip install capture-helper
pip install "capture-helper[api]"   # only for sections 9-10 (HTTP + GUI)
```

`ffmpeg` has to be on `PATH` — it is the capture backend, not an optional
accelerator: `brew install ffmpeg` on macOS (after installing `brew` from
[brew.sh](https://brew.sh/)), `sudo apt install ffmpeg` on Linux, or a Windows
build added to `PATH`. There is no PortAudio in this picture; the audio path
goes through ffmpeg too.

Every snippet below assumes these imports:

```python
import asyncio

import capture_helper as ch
```

## 1. List and filter the available sources

`list_sources` shells out to `ffmpeg -list_devices` and parses its stderr. If
`ffmpeg` is missing — or the platform is one it does not route yet — it returns
`[]` rather than raising, which makes it usable as an "is this machine
capture-ready?" probe.

```python
for s in ch.list_sources():
    print(f"{s['kind']:10s} [{s['index']}] {s['name']:40s} (driver={s['driver']})")
# camera     [0] FaceTime HD Camera                       (driver=avfoundation)
# microphone [1] MacBook Pro Microphone                   (driver=avfoundation)
# (abridged: this machine also reports two Continuity devices and a virtual
#  audio input)
```

Pass a kind to get one half of the catalogue:

```python
print(
    len(ch.list_sources("camera")),
    "camera(s),",
    len(ch.list_sources("microphone")),
    "microphone(s)",
)
# 3 camera(s), 3 microphone(s)
```

`darwin`, `linux` and `windows` are routed today. Anywhere else the catalogue
comes back empty — again without an exception.

## 2. Pick a specific device

`pick_source` returns the **first** device matching every constraint you give
it, in OS-listing order, and raises `ValueError` when nothing does.

```python
cam = ch.pick_source("camera")
print(cam["name"])
# FaceTime HD Camera

# Case-insensitive name substring — the stable way to select across machines,
# where the OS listing order varies.
mic = ch.pick_source("microphone", name_substring="macbook")
print(mic["name"])
# MacBook Pro Microphone

# Exact index in the OS listing.
print(ch.pick_source("camera", index=0))
# {'kind': 'camera', 'name': 'FaceTime HD Camera', 'index': 0,
#  'platform': 'darwin', 'driver': 'avfoundation'}
```

When nothing matches, the message says exactly what was tried and how many
candidates it had to choose from:

```python
ch.pick_source("microphone", name_substring="USB")
# ValueError: No microphone matches constraints (name_substring='USB', index=None).
# Catalog had 3 candidate(s); call list_sources('microphone') to inspect.
```

## 3. Camera → numpy BGR frames

`iter_camera_frames` yields `(H, W, 3)` BGR uint8 numpy arrays: **the same
shape and dtype as [`video_helper.extract_frames`](https://github.com/warith-harchaoui/video-helper)**.
Consumers written for the file-based path plug in unchanged.

```python
cam = ch.pick_source("camera")

# 224x224 letterboxed (aspect preserved, black pad) — a common ML input shape.
for frame in ch.iter_camera_frames(cam, output_width=224, output_height=224, fps=30, max_frames=2):
    print(frame.shape, frame.dtype)
# (224, 224, 3) uint8
# (224, 224, 3) uint8
```

**Always pass `fps`.** On macOS the `avfoundation` driver blocks rather than
failing when the frame rate is unset or set to a value the device does not
offer, so a call without `fps=` can hang indefinitely. See
[Troubleshooting](#troubleshooting) for how to list the modes a device accepts.

At least one resolution pair is required, because the raw `bgr24` pipe carries
no header and the reader has to know the frame size in advance:

```python
next(iter(ch.iter_camera_frames(cam)))
# ValueError: iter_camera_frames requires (width, height) and/or
# (output_width, output_height) so the raw byte stream can be reshaped.
# Set at least one pair, or query the device's modes ahead of time.
```

Set `width` / `height` for the capture side and `output_width` /
`output_height` for the post-decode side; set both for full control. A live
window needs OpenCV, which `capture-helper` does not depend on — install it
yourself and the frames go straight in, no conversion:

```python
import cv2  # not a capture-helper dependency

for frame in ch.iter_camera_frames(cam, width=1280, height=720, fps=30):
    cv2.imshow("preview", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break
cv2.destroyAllWindows()
```

*(Not run here: it needs a display.)*

## 4. Microphone → async PCM stream

`iter_mic_audio` yields `MicFrame` typed dicts: **the same shape as
[`podcast_helper.extract_audio_stream`](https://github.com/warith-harchaoui/podcast-helper)**.
The PCM is float32 in `[-1.0, 1.0]`, resampled to `target_sample_rate` through
ffmpeg's libswresample (anti-aliasing low-pass at the new Nyquist).

```python
async def listen():
    mic = ch.pick_source("microphone", name_substring="macbook")
    async for f in ch.iter_mic_audio(
        mic, target_sample_rate=16000, to_mono=True, frame_ms=20, max_frames=4
    ):
        print(f["pcm"].shape, f["pcm"].dtype, round(f["t_abs_s"], 3), f["voiced"])


asyncio.run(listen())
# (320,) float32 0.0 None
# (320,) float32 0.02 None
# (320,) float32 0.04 None
# (320,) float32 0.06 None
```

320 samples is 20ms at 16kHz mono. `t_abs_s` is monotonic from the moment
ffmpeg latched onto the device; `voiced` stays `None` here — a VAD downstream
is what fills it in.

Drop `max_frames` for an unbounded stream, or compute it for a bounded one:

```python
async def record_5s():
    mic = ch.pick_source("microphone", name_substring="macbook")
    return [f["pcm"] async for f in ch.iter_mic_audio(mic, max_frames=5 * 50)]


chunks = asyncio.run(record_5s())
print(len(chunks))
# 250
```

Unlike the camera, the microphone path needs no frame-rate hint: `frame_ms`
already pins the chunk size.

## 5. Compose with the video-helper / podcast-helper contracts

The point of the two iterators: **a live camera or mic plugs into any pipeline
written for the file-based helpers, with no glue code**.

```python
import numpy as np

import podcast_helper as ph


# The same VAD / ASR loop runs on:
#   - a podcast feed  (ph.extract_audio_stream)
#   - a local file    (same call)
#   - a live mic      (ch.iter_mic_audio)
async def transcribe(frames_async_iter):
    chunks = []
    async for f in frames_async_iter:
        chunks.append(f["pcm"])
        if len(chunks) * 0.02 >= 5.0:  # every 5 seconds
            audio = np.concatenate(chunks)
            print(whisper.transcribe(audio))
            chunks.clear()


# Feed-driven
asyncio.run(transcribe(ph.extract_audio_stream("https://feeds.npr.org/510289/podcast.xml")))

# Mic-driven, identical downstream code
mic = ch.pick_source("microphone")
asyncio.run(transcribe(ch.iter_mic_audio(mic, target_sample_rate=16000)))
```

*(Not run here: it needs `podcast-helper`, a network fetch and a speech model.
The two capture-helper calls in it are checked against the code; `whisper`
stands in for whatever ASR you use.)*

The same composability holds on the video side.
`video_helper.iter_frame_optical_flow` wraps any `(H, W, 3)` BGR uint8 frame
iterator and does not care whether the frames came from a file
(`video_helper.extract_frames`) or a live camera (`ch.iter_camera_frames`) —
both already share that exact contract. Live dense optical flow, no glue code,
and no new dependency on this side: capture-helper stays ffmpeg + numpy, while
the OpenCV / Torch weight sits entirely in video-helper.

```python
import video_helper as vh

cam = ch.pick_source("camera")
frames = ch.iter_camera_frames(cam, width=1280, height=720, fps=30)

# Same call as vh.iter_frame_optical_flow(vh.extract_frames("clip.mp4"), method="dis").
# Only the frame source changed, from a file to a live camera.
for flow_frame in vh.iter_frame_optical_flow(frames, method="dis"):
    bgr = flow_frame[..., :3].astype("uint8")  # back to a plain frame
    vx, vy = flow_frame[..., 3], flow_frame[..., 4]  # live per-pixel motion
```

*(Not run here: it needs `video-helper` installed. `iter_frame_optical_flow`
yields `(H, W, 5)` float32 — BGR plus `vx` / `vy` — which is what the three
slices above unpack.)*

## 6. Build the per-OS ffmpeg input string yourself

For callers wiring their own ffmpeg pipeline, the per-OS argv builder is public:

```python
cam = ch.pick_source("camera")
print(ch.ffmpeg_input_args(cam))
# ['-f', 'avfoundation', '-i', '0:none']

mic = ch.pick_source("microphone", name_substring="macbook")
print(ch.ffmpeg_input_args(mic))
# ['-f', 'avfoundation', '-i', 'none:1']
```

`avfoundation` addresses devices as `"<video>:<audio>"`, where `none` opts out
of the track you are not capturing — which is why the camera reads `0:none` and
the microphone `none:1`. Splice the fragment into a command of your own:

```python
import subprocess

cmd = [
    "ffmpeg",
    "-hide_banner",
    "-loglevel",
    "error",
    "-framerate",
    "30",  # avfoundation stalls without it
    *ch.ffmpeg_input_args(cam),
    "-frames:v",
    "1",
    "-update",
    "1",
    "-y",
    "snapshot.png",
]
subprocess.run(cmd, check=True)
print("wrote snapshot.png from", cam["name"])
# wrote snapshot.png from FaceTime HD Camera
```

`avfoundation` also prints a pixel-format list to stderr on the way through,
even at `-loglevel error`. That is chatter, not a failure: the exit status is 0
and the file is written.

`ffmpeg_input_args` raises `ValueError` for a driver it does not know, which
makes it a cheap sanity check before spawning anything.

## 7. Inspect a `Source` typed dict

```python
from capture_helper import Source  # importable for downstream typing

sources: list[Source] = ch.list_sources("camera")
print(sources[0])
# {'kind': 'camera', 'name': 'FaceTime HD Camera', 'index': 0,
#  'platform': 'darwin', 'driver': 'avfoundation'}
```

The schema: `kind` ∈ `{"camera", "microphone"}`, `driver` ∈ `{"avfoundation",
"v4l2", "dshow", "pulse", "alsa"}`, `platform` ∈ `{"darwin", "linux",
"windows"}`. `driver` is also the ffmpeg input-format flag downstream code will
use — `-f avfoundation`, `-f v4l2`, `-f dshow`, `-f pulse`, `-f alsa`.

## 8. Design, save and replay a scene

A **scene** is a reusable JSON artifact describing a multi-source composition:
a named canvas plus placed cameras / microphones with their capture parameters.
Build one in code, save it, replay it later or on another machine.

```python
scene = ch.new_scene("studio", width=1280, height=720)
scene = ch.add_source(
    scene, kind="camera", name_substring="FaceTime", x=0, y=0, w=1280, h=720, params={"fps": 30}
)
scene = ch.add_source(scene, kind="microphone", name_substring="MacBook")

print([s["label"] for s in scene["sources"]])
# ['camera 1', 'microphone 1']
```

`add_source` never mutates its input — it returns a new scene — and labels each
tile `"<kind> <n>"` unless you pass `label=` yourself.

```python
print(ch.save_scene(scene, "studio.scene.json"))
# /absolute/path/to/studio.scene.json

# Later: load it back and see how each source resolves on THIS machine.
scene = ch.load_scene("studio.scene.json")
for r in ch.resolve_scene_sources(scene):
    label = r["scene_source"]["label"]
    print(label, "->", (r["resolved"]["name"] if r["resolved"] else r["error"]))
# camera 1 -> FaceTime HD Camera
# microphone 1 -> MacBook Pro Microphone
```

`save_scene` validates on write and returns the absolute path it wrote;
`load_scene` validates on read. A source that resolves to nothing here is not
an error — `resolved` is `None` and `error` carries the reason, so one unplugged
device does not sink the whole scene.

Or let the machine seed a starter scene from whatever it has. There the label is
the full device name rather than a generated one:

```python
scene = ch.scene_from_available_devices("auto")
print(scene["name"], scene["width"], scene["height"], len(scene["sources"]))
# auto 1280 720 2
```

## 9. Live preview (JPEG / MJPEG / mic level)

These primitives power the browser GUI, and they are callable directly.

```python
cam = ch.pick_source("camera")

# A stream of JPEGs — exactly what the MJPEG endpoint concatenates.
for i, jpg in enumerate(ch.iter_camera_jpeg(cam, fps=30, max_frames=2)):
    print(i, len(jpg), "bytes")
# 0 3895 bytes
# 1 3895 bytes
```

The byte count depends on what the camera is pointed at — the auto-exposure
alone moves it between two runs a minute apart — so yours will differ. `fps`
matters for the same reason as in section 3. For a single frame, bound
the stream to one:

```python
jpg = next(iter(ch.iter_camera_jpeg(cam, fps=30, max_frames=1)))
print(len(jpg), "bytes", jpg[:3])
# 9475 bytes b'\xff\xd8\xff'
```

`snapshot_jpeg(cam)` is the shorter spelling of that, but it takes no `fps`
argument and so cannot pass one down to the camera — on an `avfoundation`
device that needs an explicit frame rate it blocks. Prefer the two lines above
until that is fixed.

`frame_to_jpeg` encodes an array you already hold, so it touches no device at
all:

```python
import numpy as np

frame = np.zeros((48, 64, 3), dtype=np.uint8)
frame[:, :, 2] = 255  # pure red, in BGR channel order
print(len(ch.frame_to_jpeg(frame)), "bytes")
# 242 bytes
```

Microphone level, for a VU meter:

```python
mic = ch.pick_source("microphone", name_substring="MacBook")
print(asyncio.run(ch.mic_level(mic)))
# {'rms': 0.0017772795343478113, 'rms_dbfs': -55.00488520104408,
#  'peak': 0.005553045775741339, 'peak_dbfs': -45.10937492936038}
```

That reading is a quiet room. `mic_level` captures roughly `window_ms` of audio
(200ms by default) and reports silence rather than raising when it gets nothing,
so a GUI polling it every few hundred milliseconds never has to catch an
exception.

Over HTTP, with the `[api]` extra:

```bash
uvicorn capture_helper.api:app --port 8000
curl http://localhost:8000/health                            # {"status":"ok"}
curl http://localhost:8000/sources
curl 'http://localhost:8000/input-args?kind=microphone&index=1'
# {"argv":["-f","avfoundation","-i","none:1"]}
curl -o thumb.jpg 'http://localhost:8000/preview/camera.jpg?output_width=480'
curl 'http://localhost:8000/preview/mic-level'
# MJPEG stream: <img src="http://localhost:8000/preview/camera.mjpeg">
```

*(The two responses shown were produced against the same app through FastAPI's
`TestClient` rather than through a listening port.)*

## 10. The browser scene configurator (`/gui`)

```bash
pip install 'capture-helper[api]'
uvicorn capture_helper.api:app --port 8000
# open http://localhost:8000/gui  (or just http://localhost:8000/)
```

Enumerate your cameras and microphones, click to drop them on the canvas,
live-preview each camera (MJPEG) and each mic (level meter), drag to arrange,
then **Save scene (JSON)**: the downloaded `.scene.json` is exactly what
`capture-helper scene-validate` / `scene-show` and `ch.load_scene(...)`
consume. `GET /gui?lang=fr` serves the same page in French. See
[GUI.md](https://github.com/warith-harchaoui/capture-helper/blob/main/GUI.md)
for the full walkthrough. Everything is local: no upload, no telemetry.

## Command line

One command line, built with `click`, nine subcommands. Flag names mirror the
library's keyword arguments.

```bash
capture-helper --help
# Commands:
#   capture-camera  Capture N frames from a camera and write raw bgr24...
#   capture-mic     Record N seconds of microphone audio to a WAV file.
#   input-args      Print the ffmpeg ``-f DRIVER -i SPEC`` argv fragment...
#   list-sources    Enumerate available capture devices (JSON output).
#   pick-source     Pick a single capture device by kind / name / index...
#   scene-auto      Emit a scene auto-populated from this host's cameras /...
#   scene-show      Load a scene and report how each source resolves on...
#   scene-validate  Validate a scene JSON file (exit 0 when well-formed).
#   stream-mic      Stream live microphone PCM (raw f32le) to stdout,...
```

Reads — the device catalogue and the ffmpeg fragment:

```bash
capture-helper list-sources --kind camera
capture-helper pick-source --kind camera --name FaceTime
# {
#   "kind": "camera",
#   "name": "FaceTime HD Camera",
#   "index": 0,
#   "platform": "darwin",
#   "driver": "avfoundation"
# }
capture-helper input-args --kind microphone --index 1
# -f avfoundation -i none:1
```

Captures — frames to a folder, audio to a WAV, audio to a pipe:

```bash
capture-helper capture-camera --output-dir frames/ \
    --output-width 480 --output-height 270 --fps 30 --max-frames 3
# frames/frame_000000.bgr24
# frames/frame_000001.bgr24
# frames/frame_000002.bgr24

capture-helper capture-mic --output mic.wav --seconds 2 --name MacBook
# mic.wav

capture-helper stream-mic --name MacBook --seconds 1 | wc -c
# 64000
```

Each `.bgr24` file is `width × height × 3` bytes — 388800 for 480×270 — with no
header, matching what `iter_camera_frames` yields. `stream-mic` writes raw
`f32le`, so one second at the default 16kHz mono is 64000 bytes; omit
`--seconds` and it runs until the consumer goes away.

Scenes — seed one from the host, check it, see how it resolves here:

```bash
capture-helper scene-auto --name studio --output studio.scene.json
capture-helper scene-validate --input studio.scene.json
# ok: studio.scene.json is a valid scene (2 source(s))
capture-helper scene-show --input studio.scene.json
```

A library exception comes back as one line on stderr plus exit 1, not a
traceback:

```bash
capture-helper pick-source --kind microphone --name USB
# Error: No microphone matches constraints (name_substring='USB', index=None).
# Catalog had 3 candidate(s); call list_sources('microphone') to inspect.
```

## Troubleshooting

**A camera call hangs and never yields a frame.** On macOS this is nearly
always the frame rate. `avfoundation` accepts only the modes the device
advertises, and an unacceptable request makes ffmpeg sit there instead of
exiting — measured on a FaceTime HD camera, which advertises 15 and 30 fps:
`fps=30` works, while leaving `fps` unset, `fps=10` and even `fps=15` all
produce nothing until the process is killed. Ask ffmpeg for an impossible mode
and read the list it prints back:

```bash
ffmpeg -hide_banner -framerate 1 -f avfoundation -i "0:none" -frames:v 1 -f null -
# Supported modes:
#   1552x1552@[15.000000 30.000000]fps
#   ...
# Error opening input: Input/output error
```

Then pass one of those numbers as `fps=` / `--fps`.

**`list_sources()` returns an empty list.** Either `ffmpeg` is not on `PATH`,
or the platform is not routed (only `darwin`, `linux` and `windows` are).
`list_sources` is deliberately best-effort and never raises, so an empty
catalogue is the only signal you get — check `shutil.which("ffmpeg")` first.

**`RuntimeError: ffmpeg exited before yielding a frame`.** The device opened
but produced nothing: OS permission denied, or the camera is held by another
app. On macOS, grant Camera / Microphone access to the program *running* Python
— Terminal, iTerm, your IDE — in System Settings → Privacy & Security; the
prompt goes to the host application, not to Python. On Linux, check your user
is in the `video` group for `/dev/video*`.

**`ValueError: iter_camera_frames requires (width, height) and/or
(output_width, output_height)`.** Raw `bgr24` off a pipe carries no header, so
the frame size has to be known before the first read. Pin a capture-side pair,
an output-side pair, or both.

**`ValueError: quality must be between 2 (best) and 31 (worst)`.** The JPEG
knob in `frame_to_jpeg` / `snapshot_jpeg` / `iter_camera_jpeg` is ffmpeg's
`-q:v` scale, which runs the *opposite* way to the 0-100 scale OpenCV and
Pillow use. `quality=90` is rejected on purpose rather than silently clamped.

**Scene files.** A missing file raises `FileNotFoundError: scene file not
found: <path>`, and a malformed one raises a `ValueError` naming the field —
`scene width must be a positive int, got 0`, for instance. Both come out of
validation, so a scene that loads is a scene the rest of the API will accept.
