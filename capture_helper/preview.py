"""
capture_helper.preview
=====================

Live-preview helpers for the scene configurator GUI. Two flavours, both built
on the existing iterators so no new capture path is introduced:

- **Camera → JPEG.** :func:`frame_to_jpeg` encodes one ``(H, W, 3)`` BGR uint8
  frame (the exact array :func:`capture_helper.iter_camera_frames` yields) to a
  JPEG byte string via a one-shot ffmpeg call. :func:`snapshot_jpeg` grabs a
  single live frame and returns it as JPEG, and :func:`iter_camera_jpeg` yields
  a stream of JPEGs suitable for an ``multipart/x-mixed-replace`` MJPEG response
  in the browser.
- **Microphone → level.** :func:`mic_level` captures a short slice of live audio
  through :func:`capture_helper.iter_mic_audio` and reduces it to an RMS / peak
  level (linear and dBFS) so the GUI can draw a live VU meter.

Why ffmpeg for JPEG (and not Pillow / OpenCV)
--------------------------------------------
ffmpeg is already a hard runtime requirement of capture-helper. Encoding the raw
BGR frame through a tiny ``ffmpeg -f rawvideo … -f mjpeg -`` call keeps the
dependency surface flat — no Pillow, no OpenCV — at the cost of one subprocess
per encode, which is negligible for preview-rate frames.

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator

import numpy as np
import os_helper as osh

from .camera import iter_camera_frames
from .mic import iter_mic_audio
from .sources import Source

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Preview defaults — small + slow enough to be cheap on the wire and the CPU.
# A browser tile rarely needs more than ~360p at ~10 fps for monitoring.
DEFAULT_PREVIEW_WIDTH: int = 480
DEFAULT_PREVIEW_HEIGHT: int = 270
DEFAULT_PREVIEW_FPS: float = 10.0
DEFAULT_JPEG_QUALITY: int = 5  # ffmpeg -q:v scale (2=best … 31=worst); 5 ≈ good.

# MJPEG multipart boundary token. The value is arbitrary but must match the
# ``Content-Type`` header the HTTP layer advertises for the stream.
MJPEG_BOUNDARY: str = "capturehelperframe"


def _ensure_ffmpeg() -> None:
    """Raise a friendly error if ffmpeg is not on PATH.

    Raises
    ------
    FileNotFoundError
        When the ``ffmpeg`` binary cannot be located.
    """
    # Centralised so every preview entry point gives the same install hint.
    if shutil.which("ffmpeg") is None:
        raise FileNotFoundError(
            "ffmpeg not found on PATH — install via 'brew install ffmpeg' "
            "(install brew thanks to https://brew.sh/), 'sudo apt install ffmpeg', "
            "or 'winget install ffmpeg'."
        )


# ---------------------------------------------------------------------------
# Camera → JPEG
# ---------------------------------------------------------------------------


def frame_to_jpeg(frame: np.ndarray, *, quality: int = DEFAULT_JPEG_QUALITY) -> bytes:
    """
    Encode a single BGR frame to a JPEG byte string via ffmpeg.

    Parameters
    ----------
    frame : numpy.ndarray
        A ``(H, W, 3)`` ``uint8`` array in OpenCV BGR channel order — exactly
        what :func:`capture_helper.iter_camera_frames` yields.
    quality : int, default 5
        ffmpeg ``-q:v`` value (``2`` best … ``31`` worst). Lower = larger file,
        better image. ``5`` is a good preview trade-off.

    Returns
    -------
    bytes
        The JPEG-encoded image.

    Raises
    ------
    ValueError
        If ``frame`` is not a ``(H, W, 3)`` uint8 array.
    FileNotFoundError
        If ffmpeg is not on PATH.
    RuntimeError
        If ffmpeg fails to encode the frame.

    Examples
    --------
    >>> import numpy as np
    >>> jpg = frame_to_jpeg(np.zeros((16, 16, 3), dtype=np.uint8))
    >>> jpg[:2] == b"\\xff\\xd8"   # JPEG SOI marker
    True
    """
    _ensure_ffmpeg()
    # Validate the array shape up front — a wrong dtype/shape would make ffmpeg
    # misread the raw byte stream and produce garbage instead of an error.
    if frame.ndim != 3 or frame.shape[2] != 3 or frame.dtype != np.uint8:
        raise ValueError(
            f"frame_to_jpeg expects a (H, W, 3) uint8 array, got shape={frame.shape} "
            f"dtype={frame.dtype}"
        )
    h, w = frame.shape[0], frame.shape[1]

    # One-shot ffmpeg: read raw bgr24 of known size on stdin, emit one JPEG on
    # stdout. ``-frames:v 1`` guarantees a single image regardless of input.
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-video_size",
        f"{w}x{h}",
        "-i",
        "-",
        "-frames:v",
        "1",
        "-q:v",
        str(quality),
        "-f",
        "mjpeg",
        "-",
    ]
    # Feed the contiguous frame bytes to ffmpeg and collect its stdout.
    proc = subprocess.run(
        cmd,
        input=np.ascontiguousarray(frame).tobytes(),
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout:
        err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffmpeg JPEG encode failed: {err or '(no stderr)'}")
    return proc.stdout


def snapshot_jpeg(
    source: Source,
    *,
    output_width: int = DEFAULT_PREVIEW_WIDTH,
    output_height: int = DEFAULT_PREVIEW_HEIGHT,
    quality: int = DEFAULT_JPEG_QUALITY,
) -> bytes:
    """
    Grab one live frame from a camera and return it as JPEG bytes.

    Parameters
    ----------
    source : Source
        A ``"camera"`` device from :func:`capture_helper.pick_source` /
        :func:`list_sources`.
    output_width, output_height : int
        Preview size (aspect-preserving fit-and-pad, per the camera iterator).
    quality : int, default 5
        JPEG quality passed to :func:`frame_to_jpeg`.

    Returns
    -------
    bytes
        A single JPEG image.

    Raises
    ------
    ValueError
        If ``source`` is not a camera.
    RuntimeError
        If no frame could be captured (permission denied / device busy).

    Examples
    --------
    >>> cam = ...  # doctest: +SKIP
    >>> jpg = snapshot_jpeg(cam)  # doctest: +SKIP
    """
    # ``max_frames=1`` makes the iterator tear ffmpeg down right after one frame.
    for frame in iter_camera_frames(
        source,
        output_width=output_width,
        output_height=output_height,
        max_frames=1,
    ):
        return frame_to_jpeg(frame, quality=quality)
    # Reaching here means ffmpeg exited before a single frame — surface it.
    raise RuntimeError("no frame captured for snapshot (device busy or permission denied?)")


def iter_camera_jpeg(
    source: Source,
    *,
    output_width: int = DEFAULT_PREVIEW_WIDTH,
    output_height: int = DEFAULT_PREVIEW_HEIGHT,
    fps: float = DEFAULT_PREVIEW_FPS,
    quality: int = DEFAULT_JPEG_QUALITY,
    max_frames: int | None = None,
) -> Iterator[bytes]:
    """
    Yield a stream of JPEG-encoded frames from a live camera.

    Each yielded item is a complete JPEG suitable for concatenation into an
    ``multipart/x-mixed-replace`` MJPEG HTTP response (see
    :func:`capture_helper.api`).

    Parameters
    ----------
    source : Source
        A ``"camera"`` device.
    output_width, output_height : int
        Preview size per frame.
    fps : float, default 10.0
        Capture-side frame rate — kept low so the preview is cheap.
    quality : int, default 5
        JPEG quality per frame.
    max_frames : int, optional
        Stop after this many frames. ``None`` = until the consumer disconnects.

    Yields
    ------
    bytes
        Successive JPEG images.

    Raises
    ------
    ValueError
        If ``source`` is not a camera.

    Examples
    --------
    >>> cam = ...  # doctest: +SKIP
    >>> for jpg in iter_camera_jpeg(cam, max_frames=3):  # doctest: +SKIP
    ...     handle(jpg)
    """
    # Delegate capture to the existing iterator (which owns ffmpeg lifecycle);
    # we only add per-frame JPEG encoding on top.
    for frame in iter_camera_frames(
        source,
        fps=fps,
        output_width=output_width,
        output_height=output_height,
        max_frames=max_frames,
    ):
        yield frame_to_jpeg(frame, quality=quality)


# ---------------------------------------------------------------------------
# Microphone → level
# ---------------------------------------------------------------------------


def rms_dbfs(pcm: np.ndarray) -> tuple[float, float]:
    """
    Compute linear RMS and its dBFS equivalent for a PCM block.

    Parameters
    ----------
    pcm : numpy.ndarray
        Float32 samples in ``[-1, 1]`` (any shape; flattened internally).

    Returns
    -------
    tuple[float, float]
        ``(rms_linear, rms_dbfs)``. ``rms_dbfs`` is clamped at ``-120.0`` for
        digital silence to avoid ``-inf``.

    Examples
    --------
    >>> import numpy as np
    >>> lin, db = rms_dbfs(np.zeros(100, dtype=np.float32))
    >>> lin == 0.0 and db == -120.0
    True
    """
    # Guard the empty case so we never divide by zero on a short read.
    flat = np.asarray(pcm, dtype=np.float64).reshape(-1)
    if flat.size == 0:
        return 0.0, -120.0
    # RMS = sqrt(mean(x^2)); dBFS = 20*log10(rms) with a silence floor.
    rms = float(np.sqrt(np.mean(flat * flat)))
    if rms <= 1e-6:
        return rms, -120.0
    db = float(20.0 * np.log10(rms))
    return rms, db


async def mic_level(
    source: Source,
    *,
    target_sample_rate: int = 16000,
    frame_ms: int = 20,
    window_ms: int = 200,
) -> dict[str, float]:
    """
    Capture a short slice of live audio and reduce it to a level reading.

    Drives :func:`capture_helper.iter_mic_audio` for roughly ``window_ms`` of
    audio, then returns RMS / peak levels — the GUI polls this to animate a VU
    meter without holding a long-lived stream open.

    Parameters
    ----------
    source : Source
        A ``"microphone"`` device.
    target_sample_rate : int, default 16000
        Sample rate for the capture (matches the iterator default).
    frame_ms : int, default 20
        Per-frame duration fed to the iterator.
    window_ms : int, default 200
        Approximate total capture window in milliseconds.

    Returns
    -------
    dict[str, float]
        ``{"rms": …, "rms_dbfs": …, "peak": …, "peak_dbfs": …}``.

    Raises
    ------
    ValueError
        If ``source`` is not a microphone.

    Examples
    --------
    >>> import asyncio  # doctest: +SKIP
    >>> mic = ...  # doctest: +SKIP
    >>> asyncio.run(mic_level(mic))  # doctest: +SKIP
    """
    # Number of frames to cover the requested window (at least one).
    n_frames = max(1, window_ms // max(1, frame_ms))
    chunks: list[np.ndarray] = []
    # Pull a bounded number of frames, then let the iterator tear ffmpeg down.
    async for frame in iter_mic_audio(
        source,
        target_sample_rate=target_sample_rate,
        frame_ms=frame_ms,
        to_mono=True,
        max_frames=n_frames,
    ):
        chunks.append(frame["pcm"])

    # No audio at all (permission denied / no device) → report silence rather
    # than raising, so the GUI meter simply stays at the floor.
    if not chunks:
        osh.warning("capture-helper: mic_level captured no audio (permission denied?)")
        return {"rms": 0.0, "rms_dbfs": -120.0, "peak": 0.0, "peak_dbfs": -120.0}

    audio = np.concatenate([c.reshape(-1) for c in chunks])
    rms, rms_db = rms_dbfs(audio)
    # Peak is the max absolute sample; its dBFS uses the same silence floor.
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    peak_db = float(20.0 * np.log10(peak)) if peak > 1e-6 else -120.0
    return {"rms": rms, "rms_dbfs": rms_db, "peak": peak, "peak_dbfs": peak_db}
