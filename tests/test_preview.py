"""
Unit tests for :mod:`capture_helper.preview`.

The JPEG-encode path is tested with a synthetic frame (ffmpeg is present on CI),
and the level maths is tested directly. Live-device capture is not exercised
here — it needs real hardware + OS permission.

Usage Example
-------------
>>> #   pytest tests/test_preview.py

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import shutil

import numpy as np
import pytest

import capture_helper as ch
from capture_helper.preview import mic_level

# ffmpeg is required for the JPEG encode path; skip cleanly if absent.
_HAS_FFMPEG = shutil.which("ffmpeg") is not None


@pytest.mark.skipif(not _HAS_FFMPEG, reason="ffmpeg not on PATH")
def test_frame_to_jpeg_encodes_synthetic_frame():
    """A synthetic BGR frame encodes to a valid JPEG (SOI marker present)."""
    # A small gradient so the encoder has real data to compress.
    frame = np.zeros((32, 48, 3), dtype=np.uint8)
    frame[:, :, 2] = np.linspace(0, 255, 48, dtype=np.uint8)  # red ramp across x
    jpg = ch.frame_to_jpeg(frame)
    # JPEG starts with the SOI marker 0xFFD8 and ends with EOI 0xFFD9.
    assert jpg[:2] == b"\xff\xd8"
    assert jpg[-2:] == b"\xff\xd9"
    assert len(jpg) > 100


def test_frame_to_jpeg_rejects_bad_shape():
    """A non ``(H, W, 3)`` uint8 array is rejected up front."""
    with pytest.raises(ValueError):
        ch.frame_to_jpeg(np.zeros((10, 10), dtype=np.uint8))
    with pytest.raises(ValueError):
        ch.frame_to_jpeg(np.zeros((10, 10, 3), dtype=np.float32))


def test_rms_dbfs_silence_floor():
    """Digital silence yields 0 linear RMS and the -120 dBFS floor (no -inf)."""
    lin, db = ch.rms_dbfs(np.zeros(256, dtype=np.float32))
    assert lin == 0.0
    assert db == -120.0


def test_rms_dbfs_full_scale():
    """A full-scale square wave reads ~0 dBFS."""
    # +/-1.0 alternating gives RMS == 1.0 == 0 dBFS.
    sig = np.ones(1000, dtype=np.float32)
    lin, db = ch.rms_dbfs(sig)
    assert lin == pytest.approx(1.0, abs=1e-6)
    assert db == pytest.approx(0.0, abs=1e-3)


def test_rms_dbfs_half_scale():
    """A constant 0.5 signal reads about -6 dBFS."""
    lin, db = ch.rms_dbfs(np.full(1000, 0.5, dtype=np.float32))
    assert lin == pytest.approx(0.5, abs=1e-6)
    assert db == pytest.approx(-6.02, abs=0.1)


@pytest.mark.asyncio
async def test_mic_level_reports_silence_instead_of_raising_on_permission_denied(monkeypatch):
    """A permission-denied/busy mic must degrade to silence, not raise.

    ``iter_mic_audio`` raises ``RuntimeError`` when it exits before a single
    frame (fixed earlier this session, matching ``iter_camera_frames``'s
    contract) — but ``mic_level`` polls it every ~200ms to drive a live VU
    meter and its own docstring says a failed capture should read as
    silence, not blow up the poll. This is the case an unguarded call used
    to leak straight to the caller.
    """

    async def _raises(*a, **k):
        raise RuntimeError("ffmpeg exited before yielding a frame")
        yield  # pragma: no cover — makes this an async generator function

    monkeypatch.setattr("capture_helper.preview.iter_mic_audio", _raises)
    level = await mic_level({"kind": "microphone"})
    assert level == {"rms": 0.0, "rms_dbfs": -120.0, "peak": 0.0, "peak_dbfs": -120.0}


# --- JPEG quality scale -----------------------------------------------------
# ffmpeg's -q:v is 2-31 with LOWER meaning better, inverted relative to the
# 0-100 higher-is-better scale OpenCV (IMWRITE_JPEG_QUALITY) and PIL
# (save(quality=)) both use -- and ffmpeg clamps out-of-range values silently.
# A caller asking for "95" therefore used to receive the worst JPEG the encoder
# can make: measured on a 128x128 noise frame, q=2 gives 30820 bytes while q=31
# and q=95 both give 5327. The request was not ignored, it was inverted.


def _frame() -> np.ndarray:
    return np.zeros((16, 16, 3), dtype=np.uint8)


@pytest.mark.parametrize("quality", [95, 100, 0, 1, 32, -5])
def test_frame_to_jpeg_rejects_an_out_of_range_quality(quality: int) -> None:
    with pytest.raises(ValueError, match="inverted"):
        ch.frame_to_jpeg(_frame(), quality=quality)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not on PATH")
@pytest.mark.parametrize("quality", [2, 5, 31])
def test_frame_to_jpeg_accepts_the_whole_legal_range(quality: int) -> None:
    """Both ends of the scale are legal, including the boundaries."""
    jpg = ch.frame_to_jpeg(_frame(), quality=quality)
    assert jpg[:2] == b"\xff\xd8"  # JPEG SOI


def test_iter_camera_jpeg_validates_before_opening_the_device() -> None:
    """It is a generator, so the check has to happen before the capture call.

    Without an early check the camera would be opened and a frame captured
    before the bad argument surfaced -- paying for a device open to learn
    about a typo.
    """
    gen = ch.iter_camera_jpeg(
        source={"kind": "camera", "id": "0", "name": "fake"},
        quality=95,
    )
    with pytest.raises(ValueError, match="inverted"):
        next(gen)
