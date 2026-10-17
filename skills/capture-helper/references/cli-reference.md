# capture-helper CLI reference

Two CLIs over the same operations. `capture-helper` (argparse) ships with the
core package; `capture-helper-click` (needs `[cli]`) is the click twin with the
same subcommands and flags.

## Device discovery

```bash
capture-helper list-sources [--kind camera|microphone] [--json]
capture-helper pick-source  [--kind camera|microphone] [--name SUBSTRING] [--index N]
capture-helper input-args   [--kind camera|microphone] [--name …|--index N]
```

- `list-sources` enumerates what the OS reports, with kind, index and name.
  An empty list on macOS almost always means the privacy prompt was declined.
- `pick-source` resolves a `Source` from a name substring or an index, and
  fails loudly rather than silently falling back to device 0.
- `input-args` prints the ffmpeg `-f … -i …` argv for a device, for when you
  are assembling an ffmpeg command yourself.

**Resolve by name, not by index.** Indices shift when a user plugs in a webcam
or a USB interface.

## Capture

```bash
capture-helper capture-camera [--name …|--index N] [--seconds S] [--fps N] \
                              [--width W] [--height H] -o OUT.mp4
capture-helper capture-mic    [--name …|--index N] [--seconds S] \
                              [--sample-rate HZ] [--channels N] -o OUT.wav
capture-helper stream-mic     [--name …|--index N] [--sample-rate HZ]
```

- `capture-camera` / `capture-mic` are **bounded**: `--seconds` is what ends
  them. Without it they run until interrupted.
- `stream-mic` writes raw PCM to stdout and never stops on its own. It is
  meant to be spawned as a subprocess by another program (a native app, an ASR
  process) that consumes the pipe and kills it when done.
- `--sample-rate 16000 --channels 1` is the suite's speech convention.

Always tell the user a device is being opened, and confirm when it is released.

## Scenes

A **scene** is a JSON file describing several live sources and their layout —
the thing the browser configurator produces. Its schema is versioned
(`SCENE_FORMAT_VERSION`) and the conventional suffix is `SCENE_SUFFIX`
(`.scene.json`).

```bash
capture-helper scene-auto     [-o studio.scene.json]   # build one from attached devices
capture-helper scene-show     SCENE.json               # resolve it against this machine
capture-helper scene-validate SCENE.json               # schema + version check
```

- `scene-auto` writes a scene populated from whatever is currently plugged in
  — the fastest way to get a valid starting file.
- `scene-show` resolves each declared source against *this* machine and
  reports which ones are missing, which is what you want before replaying a
  scene authored elsewhere.
- `scene-validate` checks the structure and the format version. **Validate any
  scene file you did not write.**

## Output contract

- `list-sources` prints one device per line (`--json` for parsing).
- Capture commands print the path they wrote.
- Scene commands print a resolution / validation report and exit non-zero on a
  bad file.
- Failures are logged through `os_helper` and exit non-zero; a partially
  written capture is removed rather than left behind.
