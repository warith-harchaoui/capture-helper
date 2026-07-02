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
from typing import Optional

import numpy as np

try:
    from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
    from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
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


# ---------------------------------------------------------------------------
# App factory + shared plumbing
# ---------------------------------------------------------------------------


app = FastAPI(
    title="Capture Helper API",
    description=(
        "HTTP surface for the capture-helper INPUT layer: enumerate cameras / "
        "microphones, resolve one device, print the ffmpeg input argv, and "
        "short-form live capture (camera snapshots as ZIP of raw bgr24 frames, "
        "mic → WAV)."
    ),
    version="0.2.0",
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


# ---------------------------------------------------------------------------
# Reads — device enumeration + selection
# ---------------------------------------------------------------------------


@app.get("/sources", tags=["reads"])
def sources(
    kind: Optional[str] = Query(
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
    name: Optional[str] = Query(None, description="Case-insensitive substring."),
    index: Optional[int] = Query(None, description="Exact index match."),
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
    name: Optional[str] = Query(None, description="Case-insensitive substring."),
    index: Optional[int] = Query(None, description="Exact index match."),
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
    name: Optional[str] = Query(None),
    index: Optional[int] = Query(None),
    width: Optional[int] = Query(None),
    height: Optional[int] = Query(None),
    fps: Optional[float] = Query(None),
    output_width: Optional[int] = Query(None),
    output_height: Optional[int] = Query(None),
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
    name: Optional[str] = Query(None),
    index: Optional[int] = Query(None),
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
