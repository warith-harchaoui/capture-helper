# GUI — Capture Helper

The **live multi-source scene configurator** served by the FastAPI app at
`GET /gui`. It is a real, shipped feature (v0.3.0) — a single self-contained
HTML page (vanilla JS + Tailwind via CDN, no build step) defined in
`capture_helper/gui.py`. Opening `http://localhost:8000/` redirects to it.

```bash
pip install 'capture-helper[api]'
uvicorn capture_helper.api:app --port 8000
# open http://localhost:8000/gui  (or just http://localhost:8000/)
```

## What it does

1. **Enumerate devices.** On load it calls `GET /sources` and lists every
   camera and microphone the OS reports, split into two palettes on the left.
2. **Compose a scene.** Click a device to place it: cameras land as tiles on a
   16:9 canvas (the first camera fills it); microphones attach as level meters
   under the canvas.
3. **Live preview.** Each camera tile shows a **live MJPEG stream** from
   `GET /preview/camera.mjpeg`, rendered directly in an `<img>` — no client-side
   decoding. Each microphone shows a **live level meter** polled from
   `GET /preview/mic-level` (green / amber / red by dBFS). When a device has no
   live feed (headless server, permission denied), the tile degrades to a
   labelled placeholder instead of erroring.
4. **Arrange.** Drag a camera tile to move it (coordinates are the scene's own
   pixel space, scaled to fit). The right-hand inspector edits the selected
   source's label and `x / y / w / z`. The canvas size (default 1280×720) is
   editable too.
5. **Save / load the design.** **Save scene (JSON)** POSTs the scene to
   `POST /scene/save`, which validates it server-side and returns a downloadable
   `<name>.scene.json`. **Load scene…** uploads a file through
   `POST /scene/load` (validated before the front-end adopts it).
   **Auto-populate** pulls a starter scene from `GET /scene`.

## The scene artifact

The saved `.scene.json` is exactly a `capture_helper.scene.Scene`: a named
canvas plus an ordered list of placed sources, each recording *how to re-select
the device* (kind + name substring + index), *where it sits* (x / y / w / h / z),
and *its capture parameters* (fps / output size / sample rate / …). It is a
portable, diffable recipe — not a live handle — so the visual design becomes a
headless, scriptable capture pipeline the CLI and library can replay:

```bash
capture-helper scene-validate --input studio.scene.json   # structural check
capture-helper scene-show     --input studio.scene.json   # who resolves here
```

```python
import capture_helper as ch
scene = ch.load_scene("studio.scene.json")
for r in ch.resolve_scene_sources(scene):
    print(r["scene_source"]["label"], "->", r["resolved"] or r["error"])
```

## Design notes

- **No build step, no framework.** One HTML string, Tailwind from a CDN, a
  single inline ES module. Reduced-motion guard, focus rings, semantic markup.
- **The GUI adds no server logic.** Every action hits the same HTTP endpoints
  the CLI / MCP surfaces use — it is purely a friendlier front door.
- **Local-first.** Every preview stream and every saved scene stays on the
  machine. No upload, no telemetry, no account.

## Not (yet) in scope

Broadcasting a composed scene OUT (RTMP / HLS / virtual webcam / live
streaming) and a real multi-source mixer that renders the scene into a single
output are on the roadmap, not implemented. Today the GUI designs and previews
scenes; the CLI / library replay them source-by-source.
