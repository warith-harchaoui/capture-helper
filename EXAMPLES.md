# Capture Helper Examples

Practical recipes for `capture-helper` v0.1.0 — **cross-platform device
enumeration + selection + live iterators** for cameras and microphones.

Every snippet assumes:

```python
import asyncio
import capture_helper as ch
```

and that `ffmpeg` is on PATH (`brew install ffmpeg` on macOS — install
`brew` thanks to [brew.sh](https://brew.sh/); `sudo apt install ffmpeg`
on Linux; a Windows build added to `PATH`).

---

## Table of Contents

1. [Setup](#setup)
2. [List all available sources](#list-all-available-sources)
3. [Filter by kind (camera / microphone)](#filter-by-kind-camera--microphone)
4. [Pick a specific device](#pick-a-specific-device)
5. [Camera → numpy BGR frames](#camera--numpy-bgr-frames)
6. [Microphone → async PCM stream](#microphone--async-pcm-stream)
7. [Compose with video-helper / podcast-helper contracts](#compose-with-video-helper--podcast-helper-contracts)
8. [Build the per-OS ffmpeg input string yourself](#build-the-per-os-ffmpeg-input-string-yourself)
9. [Inspect a `Source` typed dict](#inspect-a-source-typed-dict)
10. [Roadmap — what each version unlocks](#roadmap--what-each-version-unlocks)

---

## Setup

```bash
pip install --force-reinstall --no-cache-dir \
    git+https://github.com/warith-harchaoui/capture-helper.git@v0.1.0
```

The `list_sources` call shells out to `ffmpeg -list_devices` and parses
the stderr. If `ffmpeg` is missing, the call returns `[]` rather than
raising — handy for "is this machine capture-ready?" probes.

## List all available sources

```python
for s in ch.list_sources():
    print(f"{s['kind']:10s} [{s['index']}] {s['name']:40s} (driver={s['driver']})")
    # camera     [0] FaceTime HD Camera                       (driver=avfoundation)
    # camera     [1] iPhone Camera                            (driver=avfoundation)
    # microphone [0] Built-in Microphone                      (driver=avfoundation)
    # microphone [1] BlackHole 16ch                           (driver=avfoundation)
```

(Typical output on macOS with avfoundation.)

## Filter by kind (camera / microphone)

```python
for cam in ch.list_sources("camera"):
    print(cam["name"])
    # FaceTime HD Camera
    # iPhone Camera

for mic in ch.list_sources("microphone"):
    print(mic["name"])
    # Built-in Microphone
    # BlackHole 16ch
```

`list_sources` returns `[]` on platforms not yet covered (currently
darwin / linux / windows are supported); never raises.

## Pick a specific device

`pick_source` returns the first device matching the constraints, or
raises `ValueError` if nothing matches.

```python
# First available camera
cam = ch.pick_source("camera")
print(cam["name"])
# FaceTime HD Camera

# Pick by case-insensitive name substring (handy for stable selection
# across machines where the OS-listing order varies).
mic = ch.pick_source("microphone", name_substring="blackhole")
print(mic["name"])
# BlackHole 16ch

# Pick by exact index in the OS listing.
usb_cam = ch.pick_source("camera", index=1)
print(usb_cam["name"])
# iPhone Camera
```

When nothing matches, the error message tells the caller exactly what
was tried:

```python
ch.pick_source("microphone", name_substring="USB")
# ValueError: No microphone matches constraints
# (name_substring='USB', index=None).
# Catalog had 2 candidate(s); call list_sources('microphone') to inspect.
```

## Camera → numpy BGR frames

`iter_camera_frames` yields `(H, W, 3)` BGR uint8 numpy arrays — **same
shape and dtype as [`video_helper.extract_frames`](https://github.com/warith-harchaoui/video-helper)**.
Consumers built for the file-based path plug in unchanged.

```python
import cv2

cam = ch.pick_source("camera")

# Live preview, 720p @ 30fps, until the user presses 'q'.
for frame in ch.iter_camera_frames(cam, width=1280, height=720, fps=30):
    cv2.imshow("preview", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break
cv2.destroyAllWindows()

# 224x224 letterboxed (aspect-preserving + black pad) — common ML input shape.
for frame in ch.iter_camera_frames(cam, output_width=224, output_height=224,
                                   max_frames=10):
    # frame.shape == (224, 224, 3), dtype uint8, BGR.
    print(frame.shape, frame.dtype)
    # (224, 224, 3) uint8
```

`iter_camera_frames` requires at least one of the resolution pairs
(``(width, height)`` for the capture side or ``(output_width,
output_height)`` for the post-decode side) so the raw byte stream can
be reshaped — set both for full control.

## Microphone → async PCM stream

`iter_mic_audio` yields `MicFrame` typed dicts — **same shape as
[`podcast_helper.extract_audio_stream`](https://github.com/warith-harchaoui/podcast-helper)**.
The PCM is float32 in `[-1.0, 1.0]`, resampled to `target_sample_rate`
via ffmpeg's libswresample (anti-aliasing low-pass at the new Nyquist).

```python
async def listen():
    mic = ch.pick_source("microphone")
    async for f in ch.iter_mic_audio(mic,
                                     target_sample_rate=16000,
                                     to_mono=True,
                                     frame_ms=20):
        # f["pcm"].shape == (320,) for 20ms @ 16kHz mono.
        # f["t_abs_s"] is monotonic from the moment ffmpeg latched on.
        # f["voiced"] is None — VAD downstream fills it in if used.
        print(f["pcm"].shape, f["t_abs_s"])
        # (320,) 0.0
        # (320,) 0.02
        # (320,) 0.04
        # ...

asyncio.run(listen())
```

Pass `max_frames=N` for bounded captures:

```python
async def record_5s():
    mic = ch.pick_source("microphone")
    chunks = []
    async for f in ch.iter_mic_audio(mic, max_frames=5 * 50):  # 50 frames/s @ 20ms
        chunks.append(f["pcm"])
    return chunks

audio_chunks = asyncio.run(record_5s())
print(len(audio_chunks))
# 250
```

## Compose with video-helper / podcast-helper contracts

The whole point of v0.1.0: **a live camera/mic plugs into any pipeline
designed for the file-based helpers, with no glue code**.

```python
import asyncio
import capture_helper as ch
import podcast_helper as ph

# Same VAD / ASR loop works on:
#   - a YouTube URL (via ph.extract_audio_stream)
#   - a local file (same)
#   - a live mic (via ch.iter_mic_audio)
async def transcribe(frames_async_iter):
    chunks = []
    async for f in frames_async_iter:
        chunks.append(f["pcm"])
        if len(chunks) * 0.02 >= 5.0:           # every 5 seconds
            audio = np.concatenate(chunks)
            print(whisper.transcribe(audio))
            # "And in tonight's headlines, the Senate voted..."
            chunks.clear()

# URL-driven
asyncio.run(transcribe(ph.extract_audio_stream("https://feeds.npr.org/510289/podcast.xml")))

# Mic-driven — same downstream code
mic = ch.pick_source("microphone")
asyncio.run(transcribe(ch.iter_mic_audio(mic, target_sample_rate=16000)))
```

## Build the per-OS ffmpeg input string yourself

For users wiring their own ffmpeg pipeline, the per-OS argv builder is
exposed:

```python
import shlex, subprocess

cam = ch.pick_source("camera")
input_args = ch.ffmpeg_input_args(cam)
# ['-f', 'avfoundation', '-i', '0:none']

# One-shot snapshot.
cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error",
       *input_args,
       "-frames:v", "1", "snapshot.png"]
subprocess.run(cmd, check=True)
print("Saved snapshot.png from", cam["name"])
# Saved snapshot.png from FaceTime HD Camera
```

`ffmpeg_input_args` raises `ValueError` for unknown drivers — useful as
a sanity check before spawning ffmpeg.

## Inspect a `Source` typed dict

```python
from capture_helper import Source, SourceKind  # importable for downstream typing

sources: list[Source] = ch.list_sources()
for s in sources:
    print(s)
    # {'kind': 'camera', 'name': 'FaceTime HD Camera', 'index': 0,
    #  'platform': 'darwin', 'driver': 'avfoundation'}
    # (schema: kind ∈ {"camera", "microphone"}; driver ∈ {"avfoundation",
    #  "v4l2", "dshow", "pulse", "alsa"}; platform ∈ {"darwin", "linux",
    #  "windows"}.)
```

The `driver` field tells you the ffmpeg input format flag downstream
code will use — `-f avfoundation` / `-f v4l2` / `-f dshow` / `-f pulse` /
`-f alsa`.

## Roadmap — what each version unlocks

| Version | Layer | New capability |
|---|---|---|
| v0.0.1 | INPUT scaffold | `list_sources` + types |
| **v0.1.0** (this) | INPUT | `pick_source`, `iter_camera_frames`, `iter_mic_audio`, `ffmpeg_input_args`, `MicFrame` |
| v0.2.0 | INPUT extended | Screen / window capture + basic filter chain (noise gate, gain, scale) |
| v0.3.0 | PROCESS | `mix_audio([sources], levels=[...])`, `compose_video([sources], layout=...)` |
| v0.4.0 | PUBLISH | `emit_to_youtube_live`, `emit_to_twitch_live`, `emit_to_rtmp`, `emit_to_hls`, `emit_audio_to_icecast` |
| v0.5.0 | OUTPUT virtual | `output_to_virtual_camera`, `output_to_virtual_mic` |
| v0.6.0 | OBS integration | OBS WebSocket client (react to scene / stream events) |
