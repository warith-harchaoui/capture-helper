"""
capture_helper.camera
=====================

Live camera-frame iterator that bridges :func:`capture_helper.list_sources`
output with the **same numpy BGR (H, W, 3) uint8 contract** that
:func:`video_helper.extract_frames` uses for file-based decoding. The
intent is: *if you can drop a video file path into a pipeline, you can
drop a live camera in*.

Implementation
--------------
- Shells out to ``ffmpeg`` with the right per-OS input driver
  (``-f avfoundation`` / ``-f v4l2`` / ``-f dshow``) built by
  :func:`capture_helper.sources.ffmpeg_input_args`.
- Asks ffmpeg to decode + scale + pad to the requested output size and
  emit raw ``bgr24`` to stdout. We read fixed-size byte blocks and
  reshape into ``(H, W, 3)``.
- Pure synchronous generator — matches the
  :func:`video_helper.extract_frames` API. Async wrapping is left to the
  caller (e.g. ``asyncio.to_thread``).

Usage example
-------------
>>> import capture_helper as ch
>>> import cv2
>>> cam = ch.pick_source("camera")
>>> for frame in ch.iter_camera_frames(cam, output_width=640, output_height=360,
...                                    fps=30, max_frames=300):
...     cv2.imshow("preview", frame)
...     if cv2.waitKey(1) & 0xFF == ord("q"):
...         break

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Iterator

import numpy as np
import os_helper as osh

from .sources import Source, ffmpeg_input_args


# ---------------------------------------------------------------------------
# Constants — output pixel format
# ---------------------------------------------------------------------------

# 3 bytes per pixel (B, G, R) interleaved. Matches OpenCV's default
# in-memory layout so downstream consumers don't need a colour swap.
_BYTES_PER_PIXEL: int = 3


# ---------------------------------------------------------------------------
# Internal — ffmpeg command builder
# ---------------------------------------------------------------------------


def _build_ffmpeg_cmd(
    source: Source,
    *,
    width: int | None,
    height: int | None,
    fps: float | None,
    output_width: int | None,
    output_height: int | None,
    pad_color: str,
) -> list[str]:
    """
    Build the ffmpeg command line for a live camera capture.

    The video filter chain depends on which output size the caller
    asked for:

    - both ``output_width`` and ``output_height`` set → scale-fit (aspect
      preserved) then pad with ``pad_color`` so the output is exactly
      ``output_width × output_height`` (matches
      :func:`video_helper.extract_frames`'s scale-fit-and-pad behaviour).
    - only one set → scale to that dimension, preserving aspect ratio.
    - neither set → camera's native frame size, no scale.

    Parameters
    ----------
    source : Source
        Device dict from :func:`pick_source` / :func:`list_sources`.
    width, height : int, optional
        Capture-side resolution request — passed to ffmpeg as
        ``-video_size WxH`` *before* ``-i``. The OS driver may or may
        not honour an exact value; ffmpeg picks the closest supported
        mode otherwise.
    fps : float, optional
        Capture-side frame rate request — passed as ``-framerate`` /
        ``-r``. Same caveat as ``width/height``.
    output_width, output_height : int, optional
        Post-decode output size. See behaviour table above.
    pad_color : str
        Colour name (``"black"`` / ``"white"`` / ``"#RRGGBB"`` / …) used
        when scale-fit-and-pad applies.

    Returns
    -------
    list[str]
        The full ``ffmpeg ...`` argv ready for
        :func:`subprocess.Popen`.
    """
    # ``-nostdin -hide_banner -loglevel error`` is the suite-wide
    # ffmpeg shape — quiet, headless, single-shot.
    cmd: list[str] = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin"]

    # Capture-side knobs MUST come BEFORE -i: ffmpeg applies them to the
    # next input only when placed there.
    if width is not None and height is not None:
        cmd += ["-video_size", f"{width}x{height}"]
    if fps is not None:
        cmd += ["-framerate", str(fps)]

    # Per-OS input driver + device spec.
    cmd += ffmpeg_input_args(source)

    # Post-decode filter chain (only emitted if at least one resize knob
    # is set — leaving ffmpeg with a verbatim passthrough otherwise).
    vf: list[str] = []
    if output_width is not None and output_height is not None:
        # Aspect-preserving fit-then-pad. ``force_original_aspect_ratio=decrease``
        # downscales to fit inside the box; ``pad`` then centres and fills the
        # remainder with ``pad_color``. Matches video_helper's contract.
        vf.append(
            f"scale={output_width}:{output_height}:force_original_aspect_ratio=decrease"
        )
        vf.append(
            f"pad={output_width}:{output_height}:(ow-iw)/2:(oh-ih)/2:color={pad_color}"
        )
    elif output_width is not None:
        # Single dimension — preserve aspect ratio on the other axis.
        vf.append(f"scale={output_width}:-1")
    elif output_height is not None:
        vf.append(f"scale=-1:{output_height}")
    if vf:
        cmd += ["-vf", ",".join(vf)]

    # Output: raw bgr24 frames to stdout (matches OpenCV's channel order
    # so consumers can ``cv2.imshow`` / ``cv2.imwrite`` without a swap).
    cmd += ["-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    return cmd


# ---------------------------------------------------------------------------
# Public — live camera frame iterator
# ---------------------------------------------------------------------------


def iter_camera_frames(
    source: Source,
    *,
    width: int | None = None,
    height: int | None = None,
    fps: float | None = None,
    output_width: int | None = None,
    output_height: int | None = None,
    pad_color: str = "black",
    max_frames: int | None = None,
) -> Iterator[np.ndarray]:
    """
    Yield live camera frames as numpy BGR uint8 arrays.

    Wraps ffmpeg with the per-OS input driver picked up from
    ``source["driver"]`` and emits ``(H, W, 3)`` ``uint8`` arrays in
    OpenCV's BGR channel order — **the same shape and dtype**
    :func:`video_helper.extract_frames` yields. Consumers built for the
    file-based path therefore plug in unchanged.

    Parameters
    ----------
    source : Source
        Device dict returned by :func:`pick_source` /
        :func:`list_sources`. Its ``kind`` must be ``"camera"``.
    width, height : int, optional
        Capture-side resolution request. Passed to ffmpeg as
        ``-video_size WxH`` before the input — the OS driver picks the
        closest supported mode if the exact value isn't available.
        Leave ``None`` to use the driver's default.
    fps : float, optional
        Capture-side frame rate request. Same caveat as
        ``width / height``. Leave ``None`` for the driver default.
    output_width, output_height : int, optional
        Post-decode output size. Behaviour mirrors
        :func:`video_helper.extract_frames`:

        - both set → scale-fit (aspect preserved) then pad with
          ``pad_color`` to exactly ``output_width × output_height``;
        - one set → scale that axis, preserve aspect on the other;
        - neither set → native camera frame size.
    pad_color : str, optional
        Colour name (``"black"`` / ``"white"`` / ``"#RRGGBB"`` / …)
        used when scale-fit-and-pad applies. Default ``"black"``.
    max_frames : int, optional
        Stop after yielding this many frames. ``None`` (default) =
        unbounded — runs until the source disconnects or the consumer
        breaks.

    Yields
    ------
    numpy.ndarray
        Successive frames as ``(H, W, 3)`` BGR ``uint8`` arrays. Same
        convention as OpenCV and :func:`video_helper.extract_frames`.

    Raises
    ------
    ValueError
        If ``source["kind"]`` isn't ``"camera"``.
    FileNotFoundError
        If ``ffmpeg`` isn't on PATH.
    RuntimeError
        If ffmpeg exits before the first frame is decoded (typical when
        the OS denied camera permission or the device is in use by
        another process).

    Examples
    --------
    >>> cam = ch.pick_source("camera")
    >>> for frame in ch.iter_camera_frames(cam,
    ...                                    output_width=224, output_height=224,
    ...                                    max_frames=10):
    ...     # frame.shape == (224, 224, 3), dtype uint8, BGR.
    ...     model(frame)
    """
    # Cheap validation up front — surfacing a clear error here beats a
    # cryptic ffmpeg failure later.
    if source["kind"] != "camera":
        raise ValueError(
            f"iter_camera_frames expects a camera source, got kind={source['kind']!r}"
        )
    if shutil.which("ffmpeg") is None:
        raise FileNotFoundError(
            "ffmpeg not found on PATH — install via 'brew install ffmpeg' "
            "(install brew thanks to https://brew.sh/), 'sudo apt install ffmpeg', "
            "or grab a build from https://ffmpeg.org/download.html"
        )

    cmd = _build_ffmpeg_cmd(
        source,
        width=width,
        height=height,
        fps=fps,
        output_width=output_width,
        output_height=output_height,
        pad_color=pad_color,
    )
    osh.debug("capture-helper: camera ffmpeg cmd: %s", " ".join(cmd))

    # Frame dimensions we need to know up front to read fixed-size chunks
    # from ffmpeg's stdout. If the caller specified an explicit output
    # box, use that; otherwise fall back to the capture-side request;
    # otherwise probe the first ffmpeg frame (handled by ffprobe-less
    # routing below).
    out_w = output_width if output_width is not None else width
    out_h = output_height if output_height is not None else height
    if out_w is None or out_h is None:
        # When neither the caller nor the capture request fixed the
        # resolution, the only safe way to read raw bgr24 from a pipe
        # is to know its shape in advance. Probe via ffprobe on the
        # device — but ffprobe + a live device is fragile across OSes.
        # Cheaper: ask the caller to pin a resolution. v0.2.0 may add
        # an ffprobe-based probe; v0.1.0 keeps the contract narrow.
        raise ValueError(
            "iter_camera_frames requires (width, height) and/or "
            "(output_width, output_height) so the raw byte stream can be "
            "reshaped. Set at least one pair, or query the device's modes "
            "ahead of time."
        )

    bytes_per_frame = out_w * out_h * _BYTES_PER_PIXEL

    # ``stdout=PIPE`` for our frame bytes; ``stderr=PIPE`` so we can show
    # ffmpeg's error if the launch fails immediately.
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdout is not None  # pyright/typecheck guard
    assert proc.stderr is not None

    yielded = 0
    try:
        while True:
            # Fixed-size read — ffmpeg writes whole frames atomically
            # in rawvideo mode.
            raw = proc.stdout.read(bytes_per_frame)
            if len(raw) < bytes_per_frame:
                # Short read = ffmpeg exited / device disconnected /
                # consumer broke. Surface anything informative on stderr
                # via the logger and stop iterating.
                err = (proc.stderr.read() or b"").decode("utf-8", errors="replace").strip()
                if err:
                    logging.warning("capture-helper camera ffmpeg stderr: %s", err)
                if yielded == 0:
                    raise RuntimeError(
                        "ffmpeg exited before yielding a frame — common causes: "
                        "OS camera permission denied, device busy in another app, "
                        "or unsupported capture mode. ffmpeg stderr: " + (err or "(empty)")
                    )
                break

            # ``frombuffer`` is zero-copy but returns a read-only view;
            # ``.copy()`` gives the caller a mutable array (consistent
            # with video_helper.extract_frames).
            frame = np.frombuffer(raw, dtype=np.uint8).reshape(out_h, out_w, _BYTES_PER_PIXEL).copy()
            yield frame
            yielded += 1

            if max_frames is not None and yielded >= max_frames:
                break
    finally:
        # Always tear down the subprocess — leaking ffmpeg keeps the
        # camera locked for the rest of the OS session.
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
