# capture-helper non-CLI surfaces

`capture-helper` exposes the same capabilities through five surfaces. The Python
library and argparse CLI are always available; the others live behind optional
extras.

## 1. Python library (default)

```python
import capture_helper as ch

# --- device catalogue ---
ch.list_sources(kind=None)                         # -> list[Source]
ch.pick_source("camera", name_substring=None, index=None)  # -> Source (raises if none)
ch.ffmpeg_input_args(source)                       # -> ["-f", driver, "-i", spec]

# --- live capture iterators (STABLE contracts) ---
for frame in ch.iter_camera_frames(cam, output_width=640, output_height=360, max_frames=30):
    ...                                            # (H, W, 3) BGR uint8 — like video_helper.extract_frames
async for f in ch.iter_mic_audio(mic, target_sample_rate=16000, frame_ms=20):
    ...                                            # MicFrame{t_abs_s, pcm float32, voiced} — like podcast_helper.extract_audio_stream

# --- scene model (additive) ---
scene = ch.new_scene("studio", width=1280, height=720)
scene = ch.add_source(scene, kind="camera", name_substring="FaceTime", x=0, y=0, w=1280, h=720, params={"fps": 30})
ch.save_scene(scene, "studio.scene.json")
scene = ch.load_scene("studio.scene.json")         # validates on read
ch.validate_scene(scene)
ch.resolve_scene_sources(scene)                    # -> list[ResolvedSceneSource]
ch.scene_from_available_devices("auto")            # -> Scene seeded from this host

# --- live preview primitives (used by the GUI) ---
ch.frame_to_jpeg(frame)                            # bytes (JPEG) from one BGR frame
ch.snapshot_jpeg(cam)                              # bytes — one live JPEG
for jpg in ch.iter_camera_jpeg(cam, fps=10): ...   # stream of JPEG bytes
await ch.mic_level(mic)                            # {"rms","rms_dbfs","peak","peak_dbfs"}
```

The public API is fixed via `capture_helper.__all__`. The iterator contracts
(`iter_camera_frames`, `iter_mic_audio`, `MicFrame`) are depended on by
vocal-helper and video-helper — treat them as stable.

## 2. CLI — argparse (default) and click

- **argparse** `capture-helper <sub> …` — ships with the base package, zero
  extra deps. See `cli-reference.md`.
- **click** `capture-helper-click <sub> …` — install `capture-helper[cli]`.
  Same subcommands and flag names; nicer `--help`, shell completion.

## 3. HTTP API — FastAPI (`capture-helper[api]`)

```bash
pip install 'capture-helper[api]'
uvicorn capture_helper.api:app --host 0.0.0.0 --port 8000
# OpenAPI docs: http://localhost:8000/docs
```

Endpoints:
- `GET /health` — liveness probe → `{"status":"ok"}`.
- `GET /` — redirects to `/gui`.
- `GET /gui` — the live scene configurator (see below).
- `GET /sources?kind=` — enumerate devices (JSON).
- `GET /pick?kind=&name=&index=` — resolve one device (404 if none).
- `GET /input-args?kind=&name=&index=` — ffmpeg argv fragment (JSON).
- `GET /capture/camera?...&max_frames=N` — N frames → **zip** of raw `.bgr24`.
- `GET /capture/mic?...&seconds=S` — S seconds → **WAV** file.
- `GET /preview/camera.jpg?name=&index=` — one live **JPEG** snapshot.
- `GET /preview/camera.mjpeg?name=&index=&fps=` — live **MJPEG** stream
  (`multipart/x-mixed-replace`, renderable directly in an `<img>`).
- `GET /preview/mic-level?name=&index=` — live level JSON for a VU meter.
- `GET /scene` — a scene auto-populated from this host's devices.
- `POST /scene/save` — body = scene JSON → validated `.scene.json` download.
- `POST /scene/load` — multipart `file` upload → validated scene echoed as JSON.

Temp dirs from capture / save are cleaned via `BackgroundTasks`.

## 4. MCP server — FastAPI-MCP (`capture-helper[api,mcp]`)

```bash
pip install 'capture-helper[api,mcp]'
capture-helper-mcp                 # serves FastAPI + MCP on :8000
# or: python -m capture_helper.mcp
```

Wraps the exact FastAPI app with `fastapi_mcp` — the same endpoints become MCP
tools for any MCP-aware host. Host via `CAPTURE_HELPER_HOST` /
`CAPTURE_HELPER_PORT` env vars.

## 5. GUI — live multi-source scene configurator (`GET /gui`)

Served by the FastAPI app; no build step, no framework — a single self-contained
HTML page (Tailwind via CDN + vanilla ES-module JS) defined in
`capture_helper/gui.py`.

Workflow: the page enumerates the host's cameras / microphones (`/sources`) →
click a device to drop it on a 16:9 canvas → each camera tile shows a **live
MJPEG preview** (`/preview/camera.mjpeg`) and each mic gets a **live level
meter** polled from `/preview/mic-level` → drag camera tiles to arrange, edit
x/y/w/z + label in the inspector → **Save** the design (`/scene/save`) as a
`.scene.json` artifact, or **Load** one back (`/scene/load`), or
**Auto-populate** from `/scene`. The saved artifact is exactly what the CLI's
`scene-validate` / `scene-show` and the library's `load_scene` consume — the
visual design becomes a headless, scriptable capture recipe.

```bash
uvicorn capture_helper.api:app --port 8000
# open http://localhost:8000/gui  (or just http://localhost:8000/)
```

Local-first: every preview stream and every saved scene stays on the machine —
no upload, no telemetry.
