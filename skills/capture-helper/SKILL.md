---
name: capture-helper
description: >-
  Capture and preview live cameras and microphones with the `capture-helper`
  toolkit, and design reusable multi-source scenes. It enumerates the machine's
  cameras / microphones, resolves one device by name / index, prints the exact
  ffmpeg input argv for a device, iterates live camera frames as `(H, W, 3)` BGR
  uint8 numpy arrays (same contract as `video_helper.extract_frames`), iterates
  live microphone PCM as `MicFrame`s (same contract as
  `podcast_helper.extract_audio_stream`), snapshots a camera to JPEG, streams a
  camera as MJPEG, reads a microphone level meter, and saves / loads / replays a
  visually-designed **scene** (a JSON artifact of placed sources + layout +
  capture params). Exposed as a Python library (`import capture_helper as ch`),
  two CLIs (`capture-helper` argparse and `capture-helper-click`), a FastAPI
  HTTP surface, an MCP tool set, and a live multi-source scene configurator GUI
  at `/gui`. Local-first, ffmpeg-backed, no SaaS, no telemetry — camera and mic
  data never leave the machine.

  TRIGGER — any of: the user asks to list / enumerate / discover cameras or
  microphones ("what webcams / mics are available", "list my capture devices",
  "which camera is index 0"); to pick / select / resolve a device ("use the
  FaceTime camera", "pick the BlackHole mic", "select camera by index 1"); to
  read live camera frames into an array / ML pipeline ("stream webcam frames to
  numpy / OpenCV / my model", "grab N frames from the camera", "live camera as
  BGR arrays", "drop-in for extract_frames but from a live camera"); to read
  live microphone audio ("stream mic PCM to my ASR / VAD", "record N seconds of
  the microphone to a WAV", "live mic frames like extract_audio_stream"); to
  preview a device ("show a live camera preview / MJPEG stream", "snapshot the
  webcam to a JPEG", "live mic level meter / VU meter"); to build or run a scene
  ("design a multi-camera scene / layout", "compose several sources on a
  canvas", "save this scene / layout as a reusable config", "load / validate /
  run a scene JSON", "auto-populate a scene from my devices"); to print the
  ffmpeg input args for a device ("what's the ffmpeg -f/-i for my webcam"); or
  to run the capture API / MCP server or open the scene configurator GUI. Also
  fires on explicit mentions of the commands (`capture-helper`,
  `capture-helper-click`, `capture-helper-mcp`, subcommands `list-sources |
  pick-source | input-args | capture-camera | capture-mic | scene-auto |
  scene-validate | scene-show`) or library symbols (`list_sources`,
  `pick_source`, `ffmpeg_input_args`, `iter_camera_frames`, `iter_mic_audio`,
  `MicFrame`, `Source`, `new_scene`, `add_source`, `save_scene`, `load_scene`,
  `resolve_scene_sources`, `scene_from_available_devices`, `snapshot_jpeg`,
  `iter_camera_jpeg`, `mic_level`, `frame_to_jpeg`).

  SKIP when: the source is a FILE or URL rather than a live device — decode a
  video file's frames with video-helper, an audio file with audio-helper, a
  podcast / YouTube / RSS URL's PCM with podcast-helper, and download media with
  youtube-helper. SKIP transcription / diarization / captions (use vocal-helper),
  audio effects / stem separation (audio-helper), video editing / muxing /
  subtitle burn-in (video-helper), and anything that publishes / streams OUT to
  RTMP / HLS / a virtual webcam (not implemented — capture-helper is an INPUT
  layer only). capture-helper reads LIVE cameras and microphones; it does not
  read files, transcribe, or broadcast.
---

# capture-helper — live camera / microphone capture + scene configurator

`capture-helper` is a small, local-first Python toolkit that turns the machine's
**live cameras and microphones** into the same array / PCM contracts the rest of
the AI Helpers suite consumes, plus a **live multi-source scene configurator**
that saves a visual layout as a reusable JSON artifact. It is early-stage: the
capture iterators are stable; the scene / preview surface is new and additive.

## Before anything: verify it is installed

```bash
capture-helper --version            # argparse CLI (always installed with the pkg)
python -c "import capture_helper"   # library import check
```

If missing, install it (ffmpeg is a hard system dependency):

```bash
pip install capture-helper                 # core (library + argparse CLI)
pip install 'capture-helper[cli]'          # + click CLI twin
pip install 'capture-helper[api,mcp]'      # + FastAPI HTTP surface + MCP + GUI
```

ffmpeg must be on PATH:
- macOS 🍎 : `brew install ffmpeg` (install `brew` via [brew.sh](https://brew.sh/))
- Ubuntu 🐧 : `sudo apt install ffmpeg`
- Windows 🪟 : `winget install ffmpeg`

On macOS the OS also gates camera / microphone access — the first capture may
raise until you grant permission in System Settings → Privacy & Security.

## What it does

| Intent | CLI | Library |
|--------|-----|---------|
| List cameras / microphones | `capture-helper list-sources` | `list_sources` |
| Resolve one device | `capture-helper pick-source` | `pick_source` |
| Print ffmpeg input argv | `capture-helper input-args` | `ffmpeg_input_args` |
| Live camera → BGR frames | `capture-helper capture-camera` | `iter_camera_frames` |
| Live mic → WAV / PCM | `capture-helper capture-mic` | `iter_mic_audio` |
| Auto scene from devices | `capture-helper scene-auto` | `scene_from_available_devices` |
| Validate a scene file | `capture-helper scene-validate` | `validate_scene` / `load_scene` |
| Resolve a scene here | `capture-helper scene-show` | `resolve_scene_sources` |

Live preview primitives (used by the GUI, callable directly): `snapshot_jpeg`,
`iter_camera_jpeg`, `mic_level`, `frame_to_jpeg`.

Quick examples:

```bash
capture-helper list-sources                                   # JSON of all devices
capture-helper list-sources --kind microphone
capture-helper pick-source --kind camera --name FaceTime
capture-helper capture-camera --output-dir frames/ --output-width 640 \
    --output-height 360 --fps 30 --max-frames 30
capture-helper capture-mic --output mic.wav --seconds 3
capture-helper scene-auto --name studio --output studio.scene.json
capture-helper scene-show --input studio.scene.json           # who resolves here
```

```python
import capture_helper as ch

# Live camera → numpy BGR frames (drop-in for video_helper.extract_frames)
cam = ch.pick_source("camera")
for frame in ch.iter_camera_frames(cam, output_width=640, output_height=360, max_frames=30):
    ...  # frame.shape == (360, 640, 3), uint8, BGR

# Build and save a scene artifact
scene = ch.new_scene("studio", width=1280, height=720)
scene = ch.add_source(scene, kind="camera", name_substring="FaceTime", w=1280, h=720)
ch.save_scene(scene, "studio.scene.json")
```

For the full flag matrix and output contract, read `references/cli-reference.md`.
For the API / MCP / GUI surfaces (endpoints, the `/gui` configurator, the live
preview + scene endpoints), read `references/surfaces.md`. For the exhaustive,
auditable trigger list, read `references/triggers.md`.

## Rules of thumb

- **Live device, not a file.** capture-helper only reads cameras / microphones
  the OS reports. For files/URLs route to video-helper / audio-helper /
  podcast-helper / youtube-helper.
- **Contracts are stable.** `iter_camera_frames` yields `(H, W, 3)` BGR uint8
  (like `video_helper.extract_frames`); `iter_mic_audio` yields `MicFrame`
  (like `podcast_helper.extract_audio_stream`). vocal-helper and video-helper
  depend on these — never change their shape.
- **A camera frame iterator needs a resolution.** Pass `output_width` +
  `output_height` (or `width` + `height`) so the raw byte stream can be reshaped.
- **Scenes are portable recipes.** A saved scene records *selectors* (name /
  index) + layout + params, not a live handle; `scene-show` reports which tiles
  resolve on the current machine and which dangle.
- **Local only.** No network, no telemetry — camera / mic data never leaves the
  machine. Emphasise this when privacy matters.
- **After running, report the output path(s) / device JSON** the tool printed;
  do not re-run unless something failed.
