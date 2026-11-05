# capture-helper CLI reference

One CLI, `capture-helper`, built with click and shipped with the core package,
over the same operations the library and the HTTP surface expose. `-h` /
`--help` on any subcommand, `-V` / `--version` for the version. Devices are
chosen with `--name SUBSTRING` (case-insensitive) and/or `--index N`; with
neither, the first device the OS lists is used.

## Device discovery

```bash
capture-helper list-sources [--kind camera|microphone]
capture-helper pick-source  --kind camera|microphone [--name SUBSTRING] [--index N]
capture-helper input-args   --kind camera|microphone [--name SUBSTRING] [--index N]
```

- `list-sources` prints a JSON array of `Source` records (kind, name, index,
  …), both kinds unless `--kind` filters. An empty list on macOS almost always
  means the privacy prompt was declined.
- `pick-source` prints the one `Source` that matches, as JSON, and fails
  (exit 1) rather than falling back to another device when nothing matches.
- `input-args` prints the ffmpeg `-f DRIVER -i SPEC` fragment for the device,
  for when you are assembling an ffmpeg command yourself.

**Resolve by name, not by index.** Indices shift when a user plugs in a webcam
or a USB interface.

## Capture

```bash
capture-helper capture-camera --output-dir DIR [--name …] [--index N] \
                              [--width W] [--height H] [--fps F] \
                              [--output-width W] [--output-height H] [--pad-color black] \
                              [--max-frames 30]
capture-helper capture-mic    --output OUT.wav [--name …] [--index N] [--seconds 3] \
                              [--sample-rate 16000] [--frame-ms 20] [--mono|--no-mono]
capture-helper stream-mic     [--name …] [--index N] [--seconds S] \
                              [--sample-rate 16000] [--frame-ms 20] [--mono|--no-mono]
```

- `capture-camera` grabs `--max-frames` frames (30 by default) and writes each
  one as a raw headerless `bgr24` file, `DIR/frame_000000.bgr24` and on,
  printing every path. There is no video file: encode the frames yourself, or
  use the library's `iter_camera_frames`. `--width` / `--height` / `--fps` ask
  the device for a capture mode; `--output-width` / `--output-height` scale
  and pad after decoding. One of those two size pairs is **required**: the raw
  stream cannot be sliced into frames without it, and the command fails
  before opening the camera.
- `capture-mic` records `--seconds` (3 by default) to a 16-bit PCM WAV and
  prints its path. `--mono` (the default) downmixes; `--no-mono` records two
  channels (a mono device is duplicated onto both).
- `stream-mic` writes raw little-endian `float32` PCM to stdout, frame by
  frame, and never stops on its own unless `--seconds` is given. It is meant to
  be spawned as a subprocess by another program (a native app, an ASR process)
  that consumes the pipe and kills it when done; a closed pipe or Ctrl-C ends
  it cleanly.
- `--sample-rate 16000` with the default `--mono` is the suite's speech
  convention.

Always tell the user a device is being opened, and confirm when it is released.

## Scenes

A **scene** is a JSON file describing several live sources and their layout —
the thing the browser configurator produces. Its schema is versioned
(`SCENE_FORMAT_VERSION`, currently `1`) and the conventional suffix is
`SCENE_SUFFIX` (`.scene.json`).

```bash
capture-helper scene-auto     [--name auto] [--output studio.scene.json]
capture-helper scene-show     --input SCENE.json
capture-helper scene-validate --input SCENE.json
```

- `scene-auto` builds a scene from whatever is currently plugged in — the
  fastest way to get a valid starting file. With `--output` it writes the file
  and prints its absolute path; without, it prints the JSON.
- `scene-show` resolves each declared source against *this* machine and prints
  JSON: the scene's name and canvas, then per source its label, kind, the
  device it resolved to (or `null`) and the error when it did not. That is what
  you want before replaying a scene authored elsewhere.
- `scene-validate` checks the structure and the format version, prints
  `ok: … is a valid scene (N source(s))` and exits 0. **Validate any scene
  file you did not write.**

## Output contract

- `list-sources`, `pick-source`, `scene-show` and bare `scene-auto` print
  JSON; `input-args` prints one argv fragment.
- `capture-camera` prints one path per frame, `capture-mic` and
  `scene-auto --output` print the path they wrote.
- A library error (no matching device, a malformed scene) prints one
  `Error: …` line on stderr and exits 1. A microphone that delivers nothing
  (permission denied, device busy) is one of those library errors:
  `iter_mic_audio` raises `RuntimeError: ffmpeg exited before yielding a
  frame`, so `capture-mic` / `stream-mic` print it and exit 1.
