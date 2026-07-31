# capture-helper skill — exhaustive trigger catalogue

Auditable superset of the `description:` TRIGGER clause in `SKILL.md` (the
description is what a host model sees before loading; this file is the
human-reviewable full list). Keep the two in sync, and mirror the repo-root
`TRIGGERS.md`.

## Fire (positive triggers)

**Device discovery / selection**
- "what cameras / webcams / mics / microphones are available", "list my capture
  devices", "enumerate video / audio inputs", "which camera is index 0"
- "use the FaceTime / built-in / USB / BlackHole camera / mic", "pick a device
  by name / index", "resolve / select the default microphone"

**Live camera → arrays / pipeline**
- "stream webcam frames to numpy / OpenCV / my model", "read live camera frames"
- "grab N frames from the camera", "live camera as BGR arrays"
- "drop-in for extract_frames but from a live camera", "feed the webcam into my
  vision model / classifier"

**Live microphone → audio**
- "stream mic PCM to my ASR / VAD / transcriber", "live microphone frames"
- "record N seconds of the microphone to a WAV", "capture mic audio"
- "like extract_audio_stream but from the live mic"

**Live preview**
- "show a live camera preview", "MJPEG stream of my webcam", "snapshot the
  webcam to a JPEG", "single frame from the camera as an image"
- "live mic level / VU meter / loudness meter", "how loud is the mic right now"

**Scenes / layouts / config artifacts**
- "design a multi-camera scene / layout", "compose several sources on a canvas"
- "arrange my webcam + second cam in a scene", "picture-in-picture layout"
- "save this scene / layout as a reusable config / JSON", "export the scene"
- "load / open / validate / run a scene file", "does this scene resolve here"
- "auto-populate a scene from my devices", "starter scene from what I have"
- "open the scene configurator / capture GUI"

**ffmpeg plumbing**
- "what's the ffmpeg -f / -i for my webcam / mic", "print the input args for a
  device", "how do I open this device in ffmpeg"

**Explicit command / function mentions**
- `capture-helper`, `capture-helper-click`
- subcommands `list-sources pick-source input-args capture-camera capture-mic
  scene-auto scene-validate scene-show`
- functions `list_sources pick_source ffmpeg_input_args iter_camera_frames
  iter_mic_audio MicFrame Source new_scene add_source save_scene load_scene
  validate_scene resolve_scene_sources scene_from_available_devices
  frame_to_jpeg snapshot_jpeg iter_camera_jpeg mic_level rms_dbfs`

**Surfaces**
- "run the capture API / capture-helper server", "expose capture as HTTP"
- "open the capture GUI / scene configurator at /gui"
- "how do I install / run capture-helper"

## Do NOT fire (SKIP)

- **Frames from a video FILE** → video-helper (`extract_frames`). capture-helper
  reads live devices, not files.
- **Audio from a FILE** → audio-helper. **Audio from a URL / podcast / RSS /
  YouTube** → podcast-helper (PCM stream) / youtube-helper (download).
- **Transcription / diarization / captions / subtitles / "who spoke"** →
  vocal-helper.
- **Audio effects / stem separation / room tone / convert** → audio-helper.
- **Video editing / muxing / subtitle burn-in / resize a file** → video-helper.
- **Publishing / broadcasting OUT** (RTMP, HLS, Icecast, virtual webcam / mic,
  live-streaming to YouTube / Twitch) → not implemented; capture-helper is an
  INPUT layer only. Say so rather than pretending.

## Enforcement checklist

A trigger is "enforced" when (1) it is represented in `SKILL.md`'s `description`
TRIGGER clause so the host sees it pre-load; (2) the SKIP clause is present so
the skill does not over-fire; (3) this catalogue lists the positive and negative
buckets so a human can audit coverage against the description and the repo-root
`TRIGGERS.md`.
