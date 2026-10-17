# capture-helper non-CLI surfaces

## 1. Library

```python
import capture_helper as ch
```

Public API (`capture_helper.__all__`): `SourceKind`, `Source`, `MicFrame`,
`list_sources`, `pick_source`, `ffmpeg_input_args`, `iter_camera_frames`,
`iter_mic_audio`, `Scene`, `SceneSource`, `ResolvedSceneSource`, `new_scene`,
`add_source`, `validate_scene`, `save_scene`, `load_scene`,
`resolve_scene_sources`, `scene_from_available_devices`,
`SCENE_FORMAT_VERSION`, `SCENE_SUFFIX`, `frame_to_jpeg`, `snapshot_jpeg`,
`iter_camera_jpeg`, `mic_level`, `rms_dbfs`.

The two that matter most:

```python
for frame in ch.iter_camera_frames(source=0):  # BGR uint8 (H, W, 3)
    ...  # identical to video-helper frames

for chunk in ch.iter_mic_audio(source=0):  # MicFrame of PCM samples
    ...  # identical to podcast-helper frames
```

Both are **infinite generators** — the caller breaks out. That is deliberate:
a live device has no end-of-file.

Logging and file management route through `os_helper` — the suite convention.

## 2. CLIs — argparse (core) and click (`[cli]`)

`capture-helper` and `capture-helper-click`. See `cli-reference.md`.

## 3. HTTP API — FastAPI (`[api]`)

```bash
pip install 'capture-helper[api]'
python -m capture_helper.api        # 127.0.0.1:8000, OpenAPI docs at /docs
```

| Method | Route | Purpose |
|---|---|---|
| GET | `/health`, `/`, `/gui` | liveness and the scene configurator |
| GET | `/sources`, `/pick`, `/input-args` | device discovery |
| GET | `/capture/camera`, `/capture/mic` | bounded capture |
| GET | `/preview/camera.jpg` | one JPEG snapshot |
| GET | `/preview/camera.mjpeg` | live MJPEG stream |
| GET | `/preview/mic-level` | live level meter |
| GET | `/scene` | a scene auto-built from attached devices |
| POST | `/scene/save`, `/scene/load` | persist and restore a scene |

The preview routes exist for **humans** framing a shot or checking levels. For
programmatic work use the iterators — an MJPEG stream is a poor substitute for
`iter_camera_frames`.

## 4. MCP — `fastapi-mcp` over the *same* app (`[mcp]`)

```bash
pip install 'capture-helper[mcp]'
capture-helper-mcp                  # same app, MCP mounted at /mcp
```

`capture_helper.mcp` takes the FastAPI app from `capture_helper.api` and
mounts `FastApiMCP` on it. Every MCP tool *is* an HTTP route, so the two
surfaces cannot drift and one process serves both doors.

Register it with Claude Code:

```bash
claude mcp add capture-helper --transport http http://127.0.0.1:8000/mcp
```

**An agent with these tools can open the user's camera and microphone.** Treat
every capture tool as requiring explicit, in-the-moment consent, and say when
the device is released.

## 5. Scene configurator GUI (`[api]`)

`GET /gui` — drag live sources onto a canvas, preview them, arrange the
layout, and save it as a `.scene.json` the CLI or API can replay. This is the
surface to hand a human when the task is *designing* a multi-source setup
rather than scripting one.
