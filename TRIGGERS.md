# TRIGGERS — capture-helper

This is the user-facing, exhaustive catalogue of what `capture-helper` can do and
the natural-language phrasings, commands, functions, and situations that should
invoke it — whether you call it yourself or drive it as a Claude / OpenCode
**skill** (see [`skills/capture-helper/SKILL.md`](skills/capture-helper/SKILL.md)
and its [`references/triggers.md`](skills/capture-helper/references/triggers.md)).

`capture-helper` reads **live cameras and microphones** and lets you design
reusable multi-source **scenes**. It is local-first and ffmpeg-backed — camera
and microphone data never leave the machine. It does **not** read files/URLs,
transcribe, or broadcast out.

## Capabilities → how to invoke

| Intent | CLI | Library | API |
|--------|-----|---------|-----------|
| List cameras / microphones | `capture-helper list-sources` | `list_sources` | `GET /sources` |
| Resolve one device | `capture-helper pick-source` | `pick_source` | `GET /pick` |
| Print ffmpeg input argv | `capture-helper input-args` | `ffmpeg_input_args` | `GET /input-args` |
| Live camera → BGR frames | `capture-helper capture-camera` | `iter_camera_frames` | `GET /capture/camera` |
| Live mic → WAV / PCM | `capture-helper capture-mic` | `iter_mic_audio` | `GET /capture/mic` |
| Camera snapshot (JPEG) | — | `snapshot_jpeg` | `GET /preview/camera.jpg` |
| Camera live stream (MJPEG) | — | `iter_camera_jpeg` | `GET /preview/camera.mjpeg` |
| Microphone level meter | — | `mic_level` | `GET /preview/mic-level` |
| Auto scene from devices | `capture-helper scene-auto` | `scene_from_available_devices` | `GET /scene` |
| Validate a scene file | `capture-helper scene-validate` | `validate_scene` | `POST /scene/save` (validates) |
| Resolve a scene here | `capture-helper scene-show` | `resolve_scene_sources` | — |
| Save / load a scene | (`scene-auto --output`) | `save_scene` / `load_scene` | `POST /scene/save` · `POST /scene/load` |

Everything is also reachable through the click CLI (`capture-helper-click …`,
same flags) and the live multi-source scene configurator GUI at `GET /gui`.

## Natural-language phrasings that should fire

- **Enumerate**: "what webcams / mics are available", "list my capture devices",
  "which camera is index 0".
- **Pick**: "use the FaceTime camera", "pick the BlackHole mic", "select the
  default microphone", "resolve a device by name / index".
- **Live camera**: "stream webcam frames to numpy / OpenCV / my model", "grab N
  frames from the camera", "feed the live camera into my vision model".
- **Live mic**: "stream mic PCM to my ASR / VAD", "record 5 seconds of the
  microphone to a WAV", "live mic frames like extract_audio_stream".
- **Preview**: "show a live camera preview / MJPEG", "snapshot the webcam to a
  JPEG", "live mic level / VU meter".
- **Scene**: "design a multi-camera scene / layout", "compose several sources on
  a canvas", "picture-in-picture", "save this layout as a reusable config",
  "load / validate / run a scene JSON", "auto-populate a scene from my devices",
  "open the scene configurator".
- **ffmpeg**: "what's the ffmpeg -f / -i for my webcam", "print the input args
  for a device".
- **Surfaces**: "run the capture API / server", "expose capture as HTTP",
  "open the capture GUI".

## When NOT to use capture-helper (route elsewhere)

- **Frames from a video FILE** → [video-helper](https://github.com/warith-harchaoui/video-helper).
- **Audio from a FILE** → [audio-helper](https://github.com/warith-harchaoui/audio-helper).
- **Audio / PCM from a podcast / RSS / YouTube URL** →
  [podcast-helper](https://github.com/warith-harchaoui/podcast-helper); download
  media → [youtube-helper](https://github.com/warith-harchaoui/youtube-helper).
- **Transcription / diarization / captions / "who spoke"** →
  [vocal-helper](https://github.com/warith-harchaoui/vocal-helper).
- **Publishing / broadcasting OUT** (RTMP / HLS / virtual webcam / live
  streaming) → not implemented. capture-helper is an INPUT layer only.

## Command / function / driver reference

- Commands: `capture-helper`, `capture-helper-click`.
- Subcommands: `list-sources pick-source input-args capture-camera capture-mic
  scene-auto scene-validate scene-show`.
- Functions: `list_sources pick_source ffmpeg_input_args iter_camera_frames
  iter_mic_audio MicFrame Source new_scene add_source save_scene load_scene
  validate_scene resolve_scene_sources scene_from_available_devices
  frame_to_jpeg snapshot_jpeg iter_camera_jpeg mic_level rms_dbfs`.
- Device drivers reported per platform: `avfoundation` (macOS), `dshow`
  (Windows), `v4l2` + `pulse` (Linux).
