# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.0] - 2026-10-21

### Changed

- **The GUI's strings moved from `locales/i18n.yaml` to a `gettext`
  catalogue**, the suite-wide mechanism as of os-helper 2.6.0. The English is
  now the source, written in the markup itself as `{{_("…")}}`; the French
  lives in `capture_helper/locales/fr/LC_MESSAGES/capture_helper.po` and is
  read through `os_helper.Catalog`.

  A string the French catalogue has not caught up with renders as **readable
  English** instead of as a key. The cost is the mirror image — rewording the
  English orphans its French entry, and gettext would quietly serve the
  English — so `tests/test_gui_i18n.py` hands every source string to
  `Catalog.problems`, which names both halves of that fault.

- **The default scene name stays `untitled` in every language, and now has a
  test saying so.** It is written into a saved scene file, so translating it
  would make the contents of that file depend on the browser that produced it.
  It lives in `_JS_INVARIANTS`, outside the catalogue, precisely so no
  translator can reach it — and the new test renders both languages and
  asserts it did not move. Proven by moving it into the translated map and
  watching the suite go red.

  The language toggle is likewise computed rather than translated: its three
  parts all mean "the other language", which is data, not copy.

## [1.4.0] - 2026-10-21

### Added

- **The scene-configurator GUI speaks French and English.** Every string it
  shows now comes from `capture_helper/locales/i18n.yaml` through
  `os_helper.Locales`, the loader shared across the suite (CODING.md 21.3),
  instead of being written into the markup. `GET /gui?lang=fr|en` picks the
  language; anything the file does not carry — including a mistyped code and
  the empty default — falls back to the declared default locale, so a bad
  `?lang=` returns a page rather than a 500. A flag in the header toggles
  between the two.

  The template is tokenised (`{{TOKEN}}` in HTML, a `T` object for the
  script), so one piece of markup serves both languages and a translator never
  opens a Python file. The script's strings are injected as JSON rather than
  substituted as text: it is the encoding an apostrophe cannot break out of,
  and French copy is full of them. Nine of them carry named fields
  (`{error}`, `{cameras}`, `{mics}`, `{label}`) rather than being
  concatenated, so a translator can reorder the sentence.

  `GUI_HTML` still resolves, via a module-level `__getattr__` that renders on
  access — importers that predate this keep working, and the locale file is
  not read by callers that never serve the GUI.

  Two strings deliberately stayed out of the catalogue. The scene's default
  name (`untitled`) is written into the saved artifact, so translating it
  would make one scene carry two names depending on which language the page
  happened to be in. The inspector's `x` / `y` / `w` field labels are single
  letters that mean the same thing everywhere.

### Changed

- **The declared `os-helper` floor rises to 2.4.0**, the version that
  introduced `Locales`. It was `>=2.0.0`, which the GUI can no longer honour:
  a user installing against os-helper 2.0.x would get an `AttributeError` out
  of the `/gui` route. Nothing would have caught it — pip resolves the newest
  os-helper, never the floor, so neither CI nor a developer machine ever
  installs the version the declaration permits. `tests/test_gui_i18n.py` now
  asserts the floor against the feature it needs; verified by lowering the
  line and watching the guard fire.

### Fixed

- **Two GUI tests asserted the default language rather than the page's
  identity.** They looked for the literal `"scene configurator"`, which is no
  longer what a French default renders. They now ask the locale file what the
  page is called.

### Notes

- `[tool.setuptools.package-data]` did not exist in this project; the locale
  file is the first non-`.py` file the package ships, and it is declared there
  now. Verified the way the sibling defect was found: the built wheel was
  opened and the file found inside it. best-engine-ai-helper published wheels
  containing none of its five data files until 1.6.1 because its patterns
  resolved against the repository root rather than against a package.

## [1.3.0] - 2026-10-19

### Fixed

- **`frame_to_jpeg` silently inverted the caller's quality request.** ffmpeg's
  `-q:v` runs 2 (best) to 31 (worst), while nearly every other JPEG encoder uses
  the opposite convention: OpenCV's `IMWRITE_JPEG_QUALITY` and PIL's
  `save(quality=)` are both 0–100 with *higher* meaning better. ffmpeg clamps
  out-of-range values without a word.

  A caller arriving from `cv2.imencode(frame, [IMWRITE_JPEG_QUALITY, 95])` —
  unambiguously asking for high quality — passed `quality=95`, had it clamped to
  31, and received the worst JPEG the encoder can produce. On a 128×128 noise
  frame: `q=2` gives 30 820 bytes, `q=5` (the default) 22 521, and `q=31`,
  `q=95` and `q=100` all give 5 327. The request was not ignored, it was
  **inverted**, and nothing in the output said so.

  `quality` outside 2–31 now raises `ValueError` naming the inversion, not just
  the bound — a caller told only "must be 2–31" who then picks 31 has made the
  same mistake twice. `frame_to_jpeg` is exported in `__all__`, so this was the
  public surface.

- **`iter_camera_jpeg` validated `quality` too late.** It is a generator, so the
  check inside `frame_to_jpeg` only fired once `iter_camera_frames` had already
  opened the device and captured a frame — paying for a camera open to learn
  about a typo. The check now runs before the capture call.

### Added

- `JPEG_QUALITY_BEST` (2) and `JPEG_QUALITY_WORST` (31) name the legal bounds of
  the scale, so callers can reason about it without rediscovering the inversion.

## [1.2.5] - 2026-09-03

### Fixed

- **`POST /scene/save` path traversal**: the endpoint built its output
  filename directly from the request body's `name` field with no
  sanitization, so a value like `"../../../etc/cron.d/x"` could write a
  file outside the request's own temp directory — an arbitrary-file-write
  reachable over HTTP (the API is documented to run bound to `0.0.0.0`,
  not just localhost). Now derives the filename from a whitelist
  (alphanumerics, `-`, `_`, space only), so no directory separator can
  survive the filter regardless of how the input is crafted.

## [1.2.4] - 2026-08-24

### Fixed

- **`save_scene` wrote its JSON file non-atomically** (plain
  `Path.write_text`), so a crash or power loss mid-write could leave a
  truncated `.scene.json` — `load_scene` already degrades that to a clean
  `ValueError` rather than crashing raw, but the last known-good scene
  would still be lost. Now writes via a sibling-temp-file-then-
  `os.replace`, matching the atomic-write convention used elsewhere in the
  suite for exactly this reason.

## [1.2.3] - 2026-08-21

### Fixed

- **`_parse_dshow_devices` double-counted Windows devices**: real ffmpeg
  builds print an indented `Alternative name "..."` line right after each
  device's own quoted name (a machine-readable device path ffmpeg also
  accepts as `-i`). The parser treated that line as a second, bogus device
  because it only checks for a `"` character; that doubled the reported
  device count and shifted every later index. On Windows this meant
  `pick_source(..., index=N)` (and the CLI/API/GUI's index-based selectors
  built on it) could silently resolve to the wrong camera or microphone.
  Fixed by skipping lines that carry the `Alternative name` marker before
  the quoted-string check. Added a regression test
  (`test_parse_dshow_skips_alternative_name_lines`) built from a realistic
  fixture with alternative-name lines on every device.

## [1.2.2] - 2026-08-17

### Fixed

- **API temp-dir leak on failure**: `capture_camera`, `capture_mic`, and
  `scene_save` each created a request-scoped temp dir, then only scheduled
  its cleanup after the risky operation (camera/mic capture, or
  `save_scene`) succeeded — same bug class fixed elsewhere in the suite
  this session (audio-helper, video-helper, bucket-helper). A client
  repeatedly hitting a failing case (permission denied, device busy, disk
  error) leaked a temp dir every time. Fixed with a `_cleanup_on_error`
  context manager wrapping all three call sites; `scene_load` already did
  this correctly.
- **`mic_level`'s "report silence, don't raise" contract was dead code**:
  earlier this session `iter_mic_audio` was fixed to raise `RuntimeError`
  (instead of exiting cleanly) when it produces zero frames — but
  `mic_level`'s own `if not chunks:` fallback, meant to keep the VU-meter
  poll (`/preview/mic-level`) degrading to silence on a permission-denied
  or busy mic, could no longer be reached: the exception now propagates
  straight through, 500ing the poll instead. Fixed by having `mic_level`
  catch that `RuntimeError` itself and return the silence reading, same as
  before the dependency's contract changed.

### Docs

- `EXAMPLES.md` / `EXEMPLES.md`: added a video-side composability example to
  "Compose with video-helper / podcast-helper contracts" — piping
  `ch.iter_camera_frames(...)` straight into `video_helper.iter_frame_optical_flow(...)`
  for live dense optical flow, no glue code, no new dependency on this side.
- `EXAMPLES.md` / `EXEMPLES.md`: fixed a stale `iter_optical_flow` reference
  left over from video-helper's rename to `iter_frame_optical_flow`.
- README.md / LISEZMOI.md: the opening explainer used unglossed jargon
  (BGR uint8, PCM) with no plain-language foothold for a first-time reader;
  glossed each term on first use. Replaced a circular definition of the
  scene configurator with an actual explanation of what the JSON scene
  format buys you (portability, replay without a browser).

## [1.2.1] - 2026-08-15

### Fixed

- **`iter_mic_audio` silently returned an empty stream when ffmpeg exited
  before producing a single frame** (OS microphone permission denied,
  device busy, unsupported capture mode) — indistinguishable from "the mic
  legitimately recorded nothing yet, the stream just ended". Now raises
  `RuntimeError` with ffmpeg's stderr, the same contract `iter_camera_frames`
  already has for the analogous camera-side failure.
- **Both CLI twins let a library exception propagate as a raw Python
  traceback** (e.g. `pick_source`'s `ValueError` when no device matches).
  Both `capture-helper` and `capture-helper-click` now print `Error: ...` to
  stderr and exit 1. `capture-helper-click`'s console-script entry point now
  points at a new `cli_click.main()` wrapper (was the bare `cli` group).

## [1.2.0] - 2026-08-12

### Added

- **`stream-mic` subcommand** (argparse + click, mirrored): streams live raw
  `f32le` PCM from the microphone to stdout, unbounded by default, with no
  WAV header and nothing buffered in memory — the same convention ffmpeg
  itself uses for `-f f32le -`. `capture-mic` records a fixed duration to a
  WAV file; `stream-mic` is the live primitive for an external process
  (a native/Rust live pipeline, another language) to spawn as a subprocess
  and read from directly, the same way it would spawn ffmpeg. Exits cleanly
  (0) on Ctrl-C or when the consumer closes the pipe (`BrokenPipeError`);
  exits 2 if no audio was captured at all (e.g. permission denial).

## [1.1.1] - 2026-08-09

### Fixed

- **`test_iter_mic_audio_rejects_camera_source` was silently skipped**
  whenever `pytest-asyncio` wasn't installed, which it never was (the dev
  requirements didn't list it). Added `pytest-asyncio` to
  `requirements-dev.txt` and dropped the now-unneeded runtime skip guard;
  the test genuinely runs now.

## [1.1.0] - 2026-08-08

### Added

- **MCP surface** (`capture_helper.mcp`, `[mcp]` extra, entry point
  `capture-helper-mcp`): exposes the existing FastAPI app as MCP tools via
  `fastapi-mcp`, mirroring the pattern already shipped in `standpoint` /
  `vocal-helper` / `md2star` / `os-helper`. Closes the CLI/API/MCP surface
  gap flagged in `ai-helpers/.private/do.md` §7. Several tools (camera/mic
  capture and preview) open a real local device — flagged explicitly in the
  MCP tool description for host awareness.

## [1.0.0] - 2026-08-02

First stable release. The capture iterators (`iter_camera_frames`,
`iter_mic_audio`) and their array / PCM contracts have been stable across the
0.x line; 1.0.0 commits to them and adopts the hardened suite foundation.

### Changed

- **Requires os-helper 2.x** (`os-helper>=2.0.0,<3`, was `>=1.5.0`), adopting the
  stable AI Helpers foundation for logging and file management.
- Development status promoted to Production/Stable; the docs no longer describe
  the project as "early-stage".
- **CI is now a real gate.** The lint job dropped its `continue-on-error: true`
  and `ruff check . || true` — both silently swallowed lint failures — and now
  runs a blocking `ruff check .` plus `ruff format --check .`. The test matrix
  is trimmed to a single Python (the full sweep runs locally before push).

### Fixed

- README / LISEZMOI install commands no longer self-pin to a git tag (`@v0.3.0`);
  they use `pip install capture-helper`, which always resolves to the latest
  published release.

### Added

- `tests/test_readme_install_pin.py` guards against the stale git self-pin ever
  returning to any Markdown file.

## [0.4.1] - 2026-08-01

### Removed

- **Agent skill dropped from the public repo.** Without an MCP surface,
  the Claude/OpenCode skill (`skills/`) no longer earns its keep as public
  distribution — moved to the gitignored `.private/skills/` (kept locally
  as reference, never published). `TRIGGERS.md` stays public; its
  skill-specific framing and dead `skills/` links are removed.

## [0.4.0] - 2026-08-01

### Removed

- **MCP surface dropped.** `fastapi-mcp`'s latest release (0.4.0) is
  incompatible with the latest `mcp` SDK (`Server.__init__()` signature
  mismatch), breaking CI with no available version pairing to pin around.
  Removed `capture_helper/mcp.py`, the `capture-helper-mcp` entry point, the
  `mcp` extra, and `fastapi-mcp` from `dev`. The library, both CLIs, the
  FastAPI HTTP surface, and the browser GUI are unaffected — capture-helper
  now ships **five** surfaces instead of six. This is a MINOR bump (pre-1.0,
  removes a public entry point).

## [0.3.0] - 2026-07-20

Live multi-source scene configurator + backend, and the AI Helpers skill /
trigger surface. Everything is **additive** — the public iterator contracts
(`iter_camera_frames` `(H, W, 3)` BGR uint8; `iter_mic_audio` / `MicFrame`)
are unchanged, so vocal-helper and video-helper consumers are unaffected. This
is a MINOR bump (pre-1.0, new capability, no breaking change).

### Added

- **Scene / config model** (`capture_helper.scene`): `Scene` / `SceneSource` /
  `ResolvedSceneSource` typed dicts; `new_scene`, `add_source` (immutable
  update), `validate_scene`, `save_scene` / `load_scene` (JSON artifacts),
  `resolve_scene_sources` (map a scene onto the current machine's devices,
  degrading gracefully for dangling sources), and
  `scene_from_available_devices`. A scene records device *selectors* + canvas
  layout + capture params — a portable, scriptable capture recipe.
- **Live-preview primitives** (`capture_helper.preview`): `frame_to_jpeg`
  (BGR frame → JPEG via a one-shot ffmpeg call, no new dependency),
  `snapshot_jpeg`, `iter_camera_jpeg` (JPEG stream for MJPEG), `mic_level`
  (RMS / peak dBFS for a VU meter), and `rms_dbfs`.
- **Browser GUI** (`capture_helper.gui`, served at `GET /gui`): a live
  multi-source scene configurator — enumerate cameras + microphones, drop them
  on a canvas, live-preview each camera (MJPEG) and each microphone (level
  meter), drag / arrange, and save / load the design as a reusable JSON scene.
  Vanilla JS + Tailwind CDN, no build step. `GET /` redirects to it.
- **New FastAPI endpoints**: `GET /gui`, `GET /` (redirect),
  `GET /preview/camera.jpg`, `GET /preview/camera.mjpeg`,
  `GET /preview/mic-level`, `GET /scene`, `POST /scene/save`,
  `POST /scene/load`. The API version now reads from installed package
  metadata instead of a hand-kept literal.
- **New CLI subcommands** (both argparse and click twins): `scene-auto`,
  `scene-validate`, `scene-show`.
- **AI Helpers skill**: `skills/capture-helper/` (SKILL.md with an exhaustive
  enforced trigger + SKIP description, plus `references/{cli-reference,
  surfaces,triggers}.md`) and `skills/README.md`; installable as a Claude Skill
  and an OpenCode skill. Repo-root `TRIGGERS.md` catalogue, referenced from
  README + LISEZMOI.
- **Local-first badge + "The Promise" section** in README and LISEZMOI.

### Tests

- `tests/test_scene.py` — scene model, validation, save/load round-trip,
  graceful device resolution.
- `tests/test_preview.py` — JPEG encode (synthetic frame) + level maths.
- `tests/test_api.py` — GUI route 200 HTML, root redirect, scene save/load
  round-trip, malformed-scene rejection, new endpoints in OpenAPI.
- `tests/test_cli.py` — scene subcommands present + a scene-auto/validate
  round-trip.

### Documentation

- README / LISEZMOI: exhaustive Features section (capture layer + scene
  configurator), six-surface table (adds the browser GUI), refreshed roadmap,
  install pins bumped to v0.3.0.

## [0.2.4] - 2026-07-15

### Documentation

- Harmonize README/LISEZMOI to the AI Helpers common structure (single
  H1, PyPI + source install paths, refreshed pins to v0.2.4); no code
  changes.

## [0.2.3] - 2026-07-14

### Maintenance

- Apply the project coding standards across the package and `tests/`:
  Numpy-style docstrings on every function/class (including private and
  nested helpers), full type annotations with `from __future__ import
  annotations`, and comment density raised above the floor in every
  module. No public API or behavior changes.
- Route library logging through the os-helper logging surface
  (`osh.info/warning/error`) and adopt os-helper path/file utilities
  more widely; pin `os-helper>=1.5.0`.
- Refresh the project logo asset.


## [0.2.2] - 2026-07-08

### Documentation

- Cross-platform Install prerequisites (macOS / Ubuntu / Windows).

## [0.2.1] - 2026-07-07

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

- Type-only scaffolding for the capture/process/publish pipeline
  (Inputs → Process → Publish).
- Cross-platform device enumeration: camera / microphone / screen /
  window.

### Roadmap

- v0.1 — capture sources (iter_camera_frames, iter_mic_audio,
  iter_screen_frames, iter_window_frames)
- v0.2 — filter chains (noise gate, gain, chroma key, scale)
- v0.3 — multi-source mixer
- v0.4 — RTMP / HLS / Icecast publish (live YouTube / Twitch / podcast)
- v0.5 — virtual webcam / virtual microphone outputs
