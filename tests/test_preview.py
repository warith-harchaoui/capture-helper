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
