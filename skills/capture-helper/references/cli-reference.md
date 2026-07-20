# capture-helper CLI reference

Full command surface for the `capture-helper` skill. The argparse CLI
(`capture-helper`) ships with the base package; the click twin
(`capture-helper-click`, `[cli]` extra) mirrors the exact same subcommand and
flag names, so anything below works for both by swapping the program name.

## Subcommands

| Subcommand | Purpose | Notable flags |
|------------|---------|---------------|
| `list-sources` | Enumerate cameras / microphones (JSON) | `--kind camera\|microphone` |
| `pick-source` | Resolve one device by kind / name / index (JSON) | `--kind --name --index` |
| `input-args` | Print the ffmpeg `-f DRIVER -i SPEC` fragment | `--kind --name --index` |
| `capture-camera` | Grab N frames → raw `.bgr24` files | `--name --index --output-dir --width --height --fps --output-width --output-height --pad-color --max-frames` |
| `capture-mic` | Record N seconds → WAV | `--name --index --output --seconds --sample-rate --frame-ms --mono/--no-mono` |
| `scene-auto` | Auto-populate a scene from this host's devices | `--name --output` |
| `scene-validate` | Validate a scene JSON file (exit 0 if valid) | `--input` |
| `scene-show` | Report how each scene source resolves here | `--input` |

`capture-helper --version` and `capture-helper <sub> --help` work for every
subcommand.

## Flag details

### list-sources / pick-source / input-args
- `--kind` `camera` or `microphone`. `list-sources` omits it to list both.
- `--name` case-insensitive substring on the OS-reported device name.
- `--index` exact device index (0-based, as ffmpeg lists it).
- `pick-source` raises (non-zero exit) when nothing matches; `list-sources`
  returns `[]` and never raises.

### capture-camera
- Writes headerless raw `bgr24` frames named `frame_000000.bgr24`, one per file,
  under `--output-dir`; prints each written path.
- Requires a resolution: set `--output-width`+`--output-height` (scale-fit-and-
  pad, aspect preserved) and/or the capture-side `--width`+`--height`. Without
  either pair the raw byte stream cannot be reshaped → clear error.
- `--fps` capture-side frame rate; `--pad-color` (default `black`) fills the pad
  when fit-and-pad applies; `--max-frames` (default 30) bounds the grab.
- Turn a raw frame into a PNG later: `ffmpeg -f rawvideo -pixel_format bgr24
  -video_size WxH -i frame.bgr24 frame.png`.

### capture-mic
- Records `--seconds` (default 3.0) of PCM to `--output` WAV (int16).
- `--sample-rate` (default 16000, Whisper-native), `--frame-ms` (default 20,
  Silero-VAD native), `--mono/--no-mono` (downmix vs preserve channels).

### scene-auto
- Builds a scene with the first camera (full-canvas) + first microphone found.
  On a headless host with no devices it emits a valid empty scene.
- `--output PATH` writes the JSON (`<name>.scene.json` convention); omit to
  print to stdout.

### scene-validate
- Loads + validates the file's structure only (canvas positive, source kinds
  valid, unique ids). Does NOT check device availability. Exit 0 when valid.

### scene-show
- Loads a scene and prints a JSON report mapping each recorded source to the
  live device it resolves to on THIS machine (`resolved`) or the reason it does
  not (`error`). Use before running a scene authored elsewhere.

## Output contract (for scripting)

- `list-sources` / `pick-source` print JSON (a list / a single object).
- `input-args` prints the space-joined argv fragment (e.g. `-f avfoundation -i 0:none`).
- `capture-camera` prints one written frame path per line.
- `capture-mic` prints the output WAV path (exit 2 + stderr note if no audio
  captured — usually a permission denial).
- `scene-auto` prints the written path (with `--output`) or the scene JSON.
- `scene-validate` prints an `ok: …` line; `scene-show` prints a JSON report.

## Device drivers

`list-sources` reports a `driver` per device: `avfoundation` (macOS), `dshow`
(Windows), `v4l2` + `pulse` (Linux). `ffmpeg_input_args` / `input-args` builds
the correct per-OS `-f/-i` pair from it.
