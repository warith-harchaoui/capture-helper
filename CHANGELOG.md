# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-06-29

INPUT layer landing. v0.1.0 brings the device selector and the two live
iterators so a camera / microphone composes with the rest of the suite
without glue code.

### Added

- `pick_source(kind, *, name_substring=..., index=...)` — select a
  single device from the catalog returned by `list_sources`, with
  case-insensitive name-substring and exact-index filters. Raises
  `ValueError` (with a hint to call `list_sources`) when nothing
  matches.
- `iter_camera_frames(source, *, width=..., height=..., output_width=...,
  output_height=..., fps=..., pad_color=..., max_frames=...)` —
  synchronous generator yielding `(H, W, 3)` BGR uint8 numpy arrays
  via ffmpeg + `-f rawvideo -pix_fmt bgr24`. **Same shape and dtype as
  `video_helper.extract_frames`** so consumers wired for the file-based
  path drop in unchanged. Supports scale-fit-and-pad output sizing
  (aspect-preserving) when both output dimensions are set; aspect-
  preserving single-axis scale when only one is set; native frame size
  otherwise.
- `iter_mic_audio(source, *, target_sample_rate=16000, to_mono=True,
  frame_ms=20, max_frames=...)` — async generator yielding `MicFrame`
  typed dicts (`t_abs_s`, `pcm` as float32 in [-1, 1], `voiced=None`).
  ffmpeg's libswresample handles the resample with an anti-aliasing
  low-pass at the new Nyquist. **Same shape as
  `podcast_helper.extract_audio_stream`**.
- `MicFrame` typed dict — re-exported via the package root; structurally
  identical to `podcast_helper.streaming.PcmFrame`.
- `ffmpeg_input_args(source)` — exposed low-level helper that builds
  the per-OS `-f <driver> -i <spec>` pair (avfoundation `idx:none` /
  `none:idx`; v4l2 `/dev/videoN`; dshow `video=...` / `audio=...`;
  pulse / alsa name). Useful for users wiring their own ffmpeg
  pipelines.

### Changed

- `version` bumped to `0.1.0` in `pyproject.toml`; description updated
  to reflect the INPUT-layer release.
- Added `numpy>=1.23` to `dependencies` (used by the new camera /
  microphone reshape paths).

### Tests

- `tests/test_v01_features.py` — 21 unit tests covering `pick_source`
  filter logic, `ffmpeg_input_args` per-driver argv (avfoundation,
  v4l2, dshow, pulse), and the iterators' validation paths. Real-device
  capture is deliberately not exercised here (would require hardware
  on CI).

### Documentation



- Establish suite-wide Python coding-style mandate in `CONTRIBUTING.md`:
  numpy-style docstrings on every function and class, module-level
  docstring header (with usage example + author), full type annotations,
  generous explanatory comments.
- `EXAMPLES.md` cookbook present at the repo root and linked from
  README + LISEZMOI.
- `print(...)` in docs (EXAMPLES.md / README / LISEZMOI) is followed by
  a `#`-comment showing the expected output (doctest / REPL style);
  library `.py` code uses `osh.info` / `osh.warning` / `osh.error`
  instead of bare `print`.
- Every `brew install <pkg>` mention is paired with a brew.sh hint when
  not already obvious from context.
- `.gitignore` updated to drop accidental `*config.json` commits while
  keeping `*config.json.example` templates tracked.

### Changed

- Drop `setup.py` (sole source of truth is `pyproject.toml`).
- Add GitHub Actions CI.

## [0.0.1] - 2026-06-28

Initial scaffold.

### Features at release

- Type-only scaffolding for the OBS-inspired capture/process/publish
  pipeline (Inputs → Process → Publish).
- Cross-platform device enumeration: camera / microphone / screen /
  window.

### Roadmap

- v0.1 — capture sources (iter_camera_frames, iter_mic_audio,
  iter_screen_frames, iter_window_frames)
- v0.2 — filter chains (noise gate, gain, chroma key, scale)
- v0.3 — multi-source mixer
- v0.4 — RTMP / HLS / Icecast publish (live YouTube / Twitch / podcast)
- v0.5 — virtual webcam / virtual microphone outputs
- v0.6 — OBS WebSocket bidirectional control
