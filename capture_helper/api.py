"""
Capture Helper — FastAPI HTTP surface.

Exposes every public function in :mod:`capture_helper` as an HTTP
endpoint so `capture-helper` can be dropped behind any reverse proxy
and consumed by other services. Kept intentionally minimal:

- Query / form parameters for device selection.
- ``JSONResponse`` for device enumeration / picking / input-args (small
  structured payloads).
- ``StreamingResponse`` (ZIP) for camera snapshots — one download per
  call with the raw ``.bgr24`` frames inside.
- ``FileResponse`` for the WAV output from ``/capture/mic``.
- ``BackgroundTasks`` cleans temp files after the response has been
  streamed — no leftover garbage on disk.

Install the extra to get the runtime dependencies::

    pip install 'capture-helper[api]'

Then run the app with any ASGI server::

    uvicorn capture_helper.api:app --host 0.0.0.0 --port 8000

Usage Example
-------------
>>> # Start the server:
>>> #   uvicorn capture_helper.api:app --reload
>>> # List devices:
>>> #   curl http://localhost:8000/sources
>>> # Pick a camera by name:
>>> #   curl 'http://localhost:8000/pick?kind=camera&name=FaceTime'
>>> # Grab 10 frames at 320x240 into a ZIP:
>>> #   curl -o frames.zip \\
>>> #     'http://localhost:8000/capture/camera?output_width=320&output_height=240&max_frames=10'
>>> # Record 3s of mic PCM to a WAV:
>>> #   curl -o mic.wav 'http://localhost:8000/capture/mic?seconds=3'
>>> # Full OpenAPI docs at http://localhost:8000/docs

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import asyncio
import io
import shutil
import tempfile
import wave
import zipfile
from pathlib import Path

import numpy as np

try:
    from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, Request, UploadFile
    from fastapi.responses import (
        FileResponse,
        HTMLResponse,
        JSONResponse,
        RedirectResponse,
        StreamingResponse,
    )
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The FastAPI HTTP surface requires the [api] extra. "
        "Install with: pip install 'capture-helper[api]'"
    ) from exc

from . import (
    ffmpeg_input_args,
    iter_camera_frames,
    iter_mic_audio,
    list_sources,
    pick_source,
)
from .preview import (
    MJPEG_BOUNDARY,
    iter_camera_jpeg,
    mic_level,
    snapshot_jpeg,
)
from .scene import (
    load_scene,
    save_scene,
    scene_from_available_devices,
    validate_scene,
)

# ---------------------------------------------------------------------------
# App factory + shared plumbing
# ---------------------------------------------------------------------------


def _pkg_version() -> str:
    """Resolve the installed package version, falling back to a literal.

    Returns
    -------
    str
        The distribution version of ``capture-helper`` if importable metadata is
        present, else the current release literal (kept in sync with pyproject).
    """
    # Read from installed metadata so the API version never drifts from the
    # package version — one source of truth (pyproject) rather than a hand-kept
    # constant here.
    try:
        from importlib.metadata import version as _v

        return _v("capture-helper")
    except Exception:  # pragma: no cover — never fatal
        return "0.3.0"


app = FastAPI(
    title="Capture Helper API",
    description=(
        "HTTP surface for the capture-helper camera / microphone INPUT layer: "
        "enumerate devices, resolve one device, print the ffmpeg input argv, "
        "short-form live capture (camera snapshots as ZIP of raw bgr24 frames, "
        "mic → WAV), live preview (camera JPEG / MJPEG, mic level), and the "
        "scene configurator (save / load / auto-populate a reusable scene "
        "artifact), plus a browser GUI at /gui."
    ),
    version=_pkg_version(),
    docs_url="/docs",
    redoc_url="/redoc",
)


def _cleanup(*paths: Path | str) -> None:
    """Best-effort cleanup — never let a tidy-up failure kill a response."""
    for p in paths:
        try:
            path = Path(p)
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink(missing_ok=True)
        except Exception:
            pass


def _new_tmpdir() -> Path:
    """Create a request-scoped temp directory under the system temp root."""
    return Path(tempfile.mkdtemp(prefix="capture-helper-"))


def _zip_folder(folder: Path) -> io.BytesIO:
    """Bundle ``folder``'s contents into an in-memory ZIP for streaming."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in folder.rglob("*"):
            if p.is_file():
                zf.write(p, arcname=p.relative_to(folder))
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Simple liveness probe — no dependency check, just proves the app is up."""
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Redirect the bare root to the GUI so opening the server just works.

    Returns
    -------
    RedirectResponse
        A 307 redirect to ``/gui``. A human hitting ``http://host:port/`` almost
        always wants the scene configurator, not a 404; machines call the
        documented endpoints directly, so this is safe.
    """
    return RedirectResponse(url="/gui")


@app.get("/gui", response_class=HTMLResponse, tags=["meta"])
def gui() -> HTMLResponse:
    """Serve the self-contained single-page scene-configurator GUI.

    The page (defined in :mod:`capture_helper.gui`) is a build-step-free
    HTML + Tailwind-CDN + vanilla-JS client that calls the very same
    ``/sources`` / ``/preview/...`` / ``/scene/...`` endpoints defined here. It
    adds no server-side logic — it is purely a friendlier front door to the API.

    Returns
    -------
    HTMLResponse
        The complete HTML document (status 200, ``text/html``).
    """
    # Import here so the (large) HTML string is only loaded when the route is
    # actually hit, and so importing the API module stays cheap.
    from .gui import GUI_HTML

    return HTMLResponse(content=GUI_HTML)


# ---------------------------------------------------------------------------
# Reads — device enumeration + selection
# ---------------------------------------------------------------------------


@app.get("/sources", tags=["reads"])
def sources(
    kind: str | None = Query(
        None,
        pattern="^(camera|microphone)$",
        description="Filter to one kind; omit to list both.",
    ),
) -> JSONResponse:
    """Enumerate available capture devices as JSON."""
    return JSONResponse(list_sources(kind))


@app.get("/pick", tags=["reads"])
def pick(
    kind: str = Query(..., pattern="^(camera|microphone)$"),
    name: str | None = Query(None, description="Case-insensitive substring."),
    index: int | None = Query(None, description="Exact index match."),
) -> JSONResponse:
    """Resolve a single capture device by kind / name / index."""
    try:
        return JSONResponse(pick_source(kind, name_substring=name, index=index))
    except ValueError as exc:
        # ``pick_source`` raises ``ValueError`` when no device matches
        # — surface that as a proper HTTP 404 rather than a 500.
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/input-args", tags=["reads"])
def input_args(
    kind: str = Query(..., pattern="^(camera|microphone)$"),
    name: str | None = Query(None, description="Case-insensitive substring."),
    index: int | None = Query(None, description="Exact index match."),
) -> JSONResponse:
    """Print the ffmpeg ``-f DRIVER -i SPEC`` argv fragment for a resolved device."""
    try:
        src = pick_source(kind, name_substring=name, index=index)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JSONResponse({"argv": ffmpeg_input_args(src)})


# ---------------------------------------------------------------------------
# Actions — live capture
# ---------------------------------------------------------------------------


@app.get("/capture/camera", tags=["actions"])
def capture_camera(
    background: BackgroundTasks,
    name: str | None = Query(None),
    index: int | None = Query(None),
    width: int | None = Query(None),
    height: int | None = Query(None),
    fps: float | None = Query(None),
    output_width: int | None = Query(None),
    output_height: int | None = Query(None),
    pad_color: str = Query("black"),
    max_frames: int = Query(30, ge=1, le=10_000),
):
    """Grab ``max_frames`` frames from the selected camera. Response is a ZIP."""
    try:
        src = pick_source("camera", name_substring=name, index=index)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    tmp = _new_tmpdir()
    frames_dir = tmp / "frames"
    frames_dir.mkdir()

    # ``iter_camera_frames`` is a synchronous generator; we consume it
    # inline. The library already tears the ffmpeg subprocess down in
    # a ``finally`` block, so an early return here is safe.
    for i, frame in enumerate(
        iter_camera_frames(
            src,
            width=width,
            height=height,
            fps=fps,
            output_width=output_width,
            output_height=output_height,
            pad_color=pad_color,
            max_frames=max_frames,
        )
    ):
        (frames_dir / f"frame_{i:06d}.bgr24").write_bytes(frame.tobytes())

    buf = _zip_folder(frames_dir)
    background.add_task(_cleanup, tmp)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="frames.zip"'},
    )


async def _record_mic_to_wav(
    src: dict,
    out_path: Path,
    *,
    target_sample_rate: int,
    to_mono: bool,
    frame_ms: int,
    max_frames: int,
) -> None:
    """Consume :func:`iter_mic_audio` into a WAV file — shared with the CLIs."""
    chunks: list[np.ndarray] = []
    async for frame in iter_mic_audio(
        src,
        target_sample_rate=target_sample_rate,
        to_mono=to_mono,
        frame_ms=frame_ms,
        max_frames=max_frames,
    ):
        chunks.append(frame["pcm"])
    if not chunks:
        # Fall through — writes an empty WAV rather than raising, so
        # the client always gets a valid file back.
        pcm16 = np.zeros(0, dtype="<i2")
        n_channels = 1
    else:
        audio = np.concatenate(chunks, axis=0)
        if audio.ndim == 1:
            n_channels = 1
            interleaved = audio
        else:
            n_channels = audio.shape[1]
            interleaved = audio.reshape(-1)
        pcm16 = np.clip(interleaved * 32767.0, -32768.0, 32767.0).astype("<i2")

    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(2)
        wf.setframerate(target_sample_rate)
        wf.writeframes(pcm16.tobytes())


@app.get("/capture/mic", tags=["actions"])
def capture_mic(
    background: BackgroundTasks,
    name: str | None = Query(None),
    index: int | None = Query(None),
    seconds: float = Query(3.0, gt=0, le=600),
    sample_rate: int = Query(16000, gt=0),
    frame_ms: int = Query(20, gt=0),
    mono: bool = Query(True),
):
    """Record ``seconds`` s of PCM from the selected microphone into a WAV file."""
    try:
        src = pick_source("microphone", name_substring=name, index=index)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    tmp = _new_tmpdir()
    out_path = tmp / "mic.wav"
    frames_per_sec = max(1, 1000 // frame_ms)
    max_frames = int(seconds * frames_per_sec)
    # ``asyncio.run`` in a sync endpoint drives the async iterator to
    # completion. FastAPI's own event loop is not involved for this
    # short blocking call.
    asyncio.run(
        _record_mic_to_wav(
            src,
            out_path,
            target_sample_rate=sample_rate,
            to_mono=mono,
            frame_ms=frame_ms,
            max_frames=max_frames,
        )
    )
    background.add_task(_cleanup, tmp)
    return FileResponse(str(out_path), filename=out_path.name, media_type="audio/wav")


# ---------------------------------------------------------------------------
# Live preview — powers the scene configurator GUI tiles / meters
# ---------------------------------------------------------------------------


@app.get("/preview/camera.jpg", tags=["preview"])
def preview_camera_jpg(
    name: str | None = Query(None, description="Case-insensitive device-name substring."),
    index: int | None = Query(None, description="Exact device index."),
    output_width: int = Query(480, ge=16, le=3840),
    output_height: int = Query(270, ge=16, le=2160),
):
    """Return a single live JPEG snapshot from the selected camera.

    Parameters
    ----------
    name, index : optional
        Device selectors forwarded to :func:`capture_helper.pick_source`.
    output_width, output_height : int
        Preview size (aspect-preserving fit-and-pad).

    Returns
    -------
    Response
        A ``image/jpeg`` body (200), or HTTP 404 when no matching camera exists,
        or HTTP 503 when a frame cannot be captured (permission / busy device).
    """
    try:
        src = pick_source("camera", name_substring=name, index=index)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        # One live frame → JPEG bytes. Cheap enough for a poll-based fallback.
        jpg = snapshot_jpeg(src, output_width=output_width, output_height=output_height)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    from fastapi import Response

    return Response(content=jpg, media_type="image/jpeg")


@app.get("/preview/camera.mjpeg", tags=["preview"])
def preview_camera_mjpeg(
    name: str | None = Query(None, description="Case-insensitive device-name substring."),
    index: int | None = Query(None, description="Exact device index."),
    output_width: int = Query(480, ge=16, le=3840),
    output_height: int = Query(270, ge=16, le=2160),
    fps: float = Query(10.0, gt=0, le=60),
    max_frames: int | None = Query(
        None, description="Stop after N frames; omit = until disconnect."
    ),
):
    """Stream the selected camera as ``multipart/x-mixed-replace`` MJPEG.

    The browser renders this directly in an ``<img>`` tag, giving a live preview
    tile with no client-side decoding. The stream ends when the client
    disconnects (or after ``max_frames`` if given).

    Parameters
    ----------
    name, index : optional
        Device selectors forwarded to :func:`capture_helper.pick_source`.
    output_width, output_height : int
        Per-frame preview size.
    fps : float
        Preview frame rate (kept low by default to stay cheap).
    max_frames : int, optional
        Bound the stream length.

    Returns
    -------
    StreamingResponse
        A ``multipart/x-mixed-replace`` body, or HTTP 404 when no camera matches.
    """
    try:
        src = pick_source("camera", name_substring=name, index=index)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    def _gen():
        """Yield MJPEG multipart parts, one per JPEG frame.

        Yields
        ------
        bytes
            A boundary + headers + JPEG payload chunk per frame.
        """
        # Each part is: boundary, content-type/length headers, blank line, JPEG.
        try:
            for jpg in iter_camera_jpeg(
                src,
                output_width=output_width,
                output_height=output_height,
                fps=fps,
                max_frames=max_frames,
            ):
                yield (
                    b"--"
                    + MJPEG_BOUNDARY.encode()
                    + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
                    + str(len(jpg)).encode()
                    + b"\r\n\r\n"
                    + jpg
                    + b"\r\n"
                )
        except (RuntimeError, FileNotFoundError):
            # Device vanished / permission denied mid-stream — end the response
            # cleanly rather than 500ing a long-lived connection.
            return

    return StreamingResponse(
        _gen(),
        media_type=f"multipart/x-mixed-replace; boundary={MJPEG_BOUNDARY}",
    )


@app.get("/preview/mic-level", tags=["preview"])
def preview_mic_level(
    name: str | None = Query(None, description="Case-insensitive device-name substring."),
    index: int | None = Query(None, description="Exact device index."),
    sample_rate: int = Query(16000, gt=0),
    window_ms: int = Query(200, gt=0, le=2000),
) -> JSONResponse:
    """Capture a short slice of live audio and return its level (for a VU meter).

    Parameters
    ----------
    name, index : optional
        Device selectors forwarded to :func:`capture_helper.pick_source`.
    sample_rate : int
        Capture sample rate.
    window_ms : int
        Approximate capture window used to compute the level.

    Returns
    -------
    JSONResponse
        ``{"rms", "rms_dbfs", "peak", "peak_dbfs"}``, or HTTP 404 when no
        matching microphone exists.
    """
    try:
        src = pick_source("microphone", name_substring=name, index=index)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    # The level helper is async; drive it to completion in this sync endpoint.
    level = asyncio.run(mic_level(src, target_sample_rate=sample_rate, window_ms=window_ms))
    return JSONResponse(level)


# ---------------------------------------------------------------------------
# Scene configurator — save / load / auto-populate the reusable artifact
# ---------------------------------------------------------------------------


@app.get("/scene", tags=["scene"])
def scene_auto() -> JSONResponse:
    """Return a starter scene auto-populated from this host's live devices.

    Returns
    -------
    JSONResponse
        A valid scene (first camera full-canvas + first microphone, if any).
        Empty of sources on a headless host with no devices.
    """
    return JSONResponse(scene_from_available_devices())


@app.post("/scene/save", tags=["scene"])
async def scene_save(background: BackgroundTasks, request: Request):
    """Validate a posted scene and return it as a downloadable JSON artifact.

    The request body is the scene JSON (as produced by the GUI). It is validated
    server-side (the same validation the CLI uses) and written to a temp file,
    then streamed back as a ``.scene.json`` download.

    Parameters
    ----------
    background : BackgroundTasks
        Used to clean the temp file after the response is sent.
    request : Request
        Carries the raw scene JSON body.

    Returns
    -------
    FileResponse
        The validated scene as a downloadable file, or HTTP 400 on a bad scene.
    """
    # Parse + validate the posted scene; a malformed body is a 400, not a 500.
    try:
        payload = await request.json()
        validate_scene(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid scene: {exc}") from exc

    tmp = _new_tmpdir()
    name = str(payload.get("name") or "scene")
    out_path = tmp / f"{name}.scene.json"
    # Reuse the library save so the on-disk shape matches the CLI exactly.
    save_scene(payload, out_path)
    background.add_task(_cleanup, tmp)
    return FileResponse(
        str(out_path),
        filename=out_path.name,
        media_type="application/json",
    )


@app.post("/scene/load", tags=["scene"])
async def scene_load(file: UploadFile = File(...)) -> JSONResponse:
    """Validate an uploaded scene file and echo it back as JSON.

    Lets the GUI round-trip a scene through the server's own validator (so a
    hand-edited file is rejected with a clear message before the front-end
    adopts it).

    Parameters
    ----------
    file : UploadFile
        The uploaded ``.scene.json`` file.

    Returns
    -------
    JSONResponse
        The validated scene, or HTTP 400 when the file is not a valid scene.
    """
    tmp = _new_tmpdir()
    dest = tmp / "uploaded.scene.json"
    try:
        # Persist the upload, then run it through the library loader/validator.
        dest.write_bytes(await file.read())
        scene = load_scene(dest)
        return JSONResponse(scene)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid scene file: {exc}") from exc
    finally:
        _cleanup(tmp)
