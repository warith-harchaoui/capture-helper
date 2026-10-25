---
name: capture-helper
description: >-
  Turn a live camera or microphone into data the rest of the AI Helpers suite
  already consumes, and arrange several live sources into a reusable scene.
  Enumerate the machine's cameras and microphones, pick one by name or index,
  grab camera frames as BGR uint8 arrays (same shape as video-helper's
  extract_frames), stream microphone PCM chunks (same shape as
  podcast-helper's extract_audio_stream), snapshot a JPEG, read a live mic
  level, and build / validate / save / load JSON scene files. Use when the user
  says "list my cameras / microphones", "which webcam / input device do I
  have", "take a snapshot from the webcam", "record from the mic", "live
  preview", "capture from my camera", "mic level / VU meter", "build a scene
  with two cameras", or names `capture-helper`,
  `capture-helper-mcp`, `import capture_helper as ch`. Do NOT use to process an
  existing file (video-helper / audio-helper), transcribe speech
  (vocal-helper), or download media (youtube-helper).
license: BSD-3-Clause
metadata:
  author: Warith Harchaoui
  package: capture-helper
  suite: ai-helpers
  homepage: https://deraison.ai/ai-helpers
---

# capture-helper — live camera and microphone as suite-shaped data

`capture-helper` is the suite's **live input** layer. Its promise is shape
compatibility: `iter_camera_frames` yields the same BGR uint8 arrays as
video-helper's `extract_frames`, and `iter_mic_audio` yields the same PCM
chunks as podcast-helper's `extract_audio_stream`. Code written against a
recorded file runs unchanged against a live device. On top of those two
iterators sits a scene configurator — drag several live sources onto a canvas
in the browser and save the layout as JSON the CLI or API can replay.

## ⚠️ Consent comes first

This skill opens a **camera or a microphone**. Before starting any capture:
tell the user which device you are about to open and why, and get a clear yes.
Say explicitly when the capture stops. Never start a recording as a side effect
of some other task, and never leave one running after the task is done.

## Before anything: verify it is installed

```bash
capture-helper list-sources         # the CLI + proves device access works
python -c "import capture_helper"   # library import check
ffmpeg -version                     # hard system dependency
```

Install:

```bash
pip install capture-helper                 # core: iterators + click CLI
pip install 'capture-helper[api]'          # + FastAPI HTTP surface and scene GUI
pip install 'capture-helper[mcp]'          # + MCP tools over the same app
```

On macOS the first run triggers the system camera / microphone permission
prompt. If `list-sources` comes back empty, that prompt was declined — the fix
is in System Settings › Privacy & Security, not in the code.

## What it does, and how to invoke it

| Intent | CLI | Library |
|---|---|---|
| What devices exist | `capture-helper list-sources` | `list_sources` |
| Choose one by name or index | `capture-helper pick-source` | `pick_source` |
| The ffmpeg args for a device | `capture-helper input-args` | `ffmpeg_input_args` |
| Grab camera frames | `capture-helper capture-camera` | `iter_camera_frames` |
| Grab microphone audio | `capture-helper capture-mic` | `iter_mic_audio` |
| Stream mic audio continuously | `capture-helper stream-mic` | `iter_mic_audio` |
| Build a scene from what is plugged in | `capture-helper scene-auto` | `scene_from_available_devices` |
| Inspect / check a scene file | `capture-helper scene-show`, `scene-validate` | `load_scene`, `validate_scene` |

Quick examples:

```bash
capture-helper list-sources                      # cameras and mics, with indices
capture-helper capture-camera --seconds 5 -o out.mp4
capture-helper capture-mic --seconds 10 -o out.wav
capture-helper scene-auto -o studio.scene.json
```

```python
import capture_helper as ch

for frame in ch.iter_camera_frames(source=0):  # BGR uint8, like video-helper
    ...  # break to stop the capture

for chunk in ch.iter_mic_audio(source=0):  # MicFrame PCM, like podcast-helper
    ...
```

Both iterators are infinite generators: **the caller decides when to stop**.
Break out of the loop, or wrap them with a duration guard.

For the full flag matrix and the scene-file format, read
`references/cli-reference.md`. For the HTTP API, MCP tools and the scene GUI,
read `references/surfaces.md`. For the exhaustive trigger list, read
`references/triggers.md`.

## Rules of thumb

- **Enumerate before you open.** `list-sources` first, then `pick-source` by
  name — hard-coded device indices move when a user plugs in a webcam.
- **The shape compatibility is the point.** Do not reshape or convert frames to
  hand them to video-helper, or PCM chunks to hand them to vocal-helper; they
  already match.
- **Stop explicitly.** The iterators never end on their own. A capture left
  running holds the device and the user's camera light stays on.
- **A scene is just JSON.** `scene-auto` writes one from the devices currently
  attached; `scene-validate` checks it against `SCENE_FORMAT_VERSION` before
  anything tries to replay it. Validate a scene you did not write.
- **Live preview is for humans.** `/preview/camera.mjpeg` and
  `/preview/mic-level` exist so a person can frame a shot or check levels —
  use the iterators, not the preview routes, for programmatic work.
- **After a capture, report the output path and the real duration** — and say
  the device has been released.
