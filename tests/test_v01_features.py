"""
Smoke tests for v0.1.0 — pick_source + ffmpeg_input_args + iterator
contracts (no real device required).

These tests don't ask for real hardware: they monkeypatch
``list_sources`` to seed the catalog, exercise the selector and
per-OS argv builder, and verify that the iterator entry points
exist with the right shape.
"""

from __future__ import annotations

from typing import Iterator

import pytest

import capture_helper as ch
from capture_helper.sources import ffmpeg_input_args, pick_source


# ---------------------------------------------------------------------------
# pick_source — filter logic
# ---------------------------------------------------------------------------


def _seed_catalog(monkeypatch: pytest.MonkeyPatch, sources: list[ch.Source]) -> None:
    """Replace ``list_sources`` so ``pick_source`` reads from ``sources``."""

    def _fake(kind: ch.SourceKind | None = None) -> list[ch.Source]:
        return [s for s in sources if kind is None or s["kind"] == kind]

    monkeypatch.setattr("capture_helper.sources.list_sources", _fake)


def test_pick_source_first_match(monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_catalog(
        monkeypatch,
        [
            {"kind": "camera", "name": "FaceTime HD Camera", "index": 0,
             "platform": "darwin", "driver": "avfoundation"},
            {"kind": "camera", "name": "iPhone Camera", "index": 1,
             "platform": "darwin", "driver": "avfoundation"},
        ],
    )
    cam = pick_source("camera")
    assert cam["name"] == "FaceTime HD Camera"


def test_pick_source_name_substring_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_catalog(
        monkeypatch,
        [
            {"kind": "microphone", "name": "Built-in Microphone", "index": 0,
             "platform": "darwin", "driver": "avfoundation"},
            {"kind": "microphone", "name": "BlackHole 16ch", "index": 1,
             "platform": "darwin", "driver": "avfoundation"},
        ],
    )
    mic = pick_source("microphone", name_substring="blackhole")
    assert mic["name"] == "BlackHole 16ch"


def test_pick_source_by_index(monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_catalog(
        monkeypatch,
        [
            {"kind": "camera", "name": "A", "index": 0,
             "platform": "linux", "driver": "v4l2"},
            {"kind": "camera", "name": "B", "index": 1,
             "platform": "linux", "driver": "v4l2"},
        ],
    )
    cam = pick_source("camera", index=1)
    assert cam["name"] == "B"


def test_pick_source_empty_catalog_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_catalog(monkeypatch, [])
    with pytest.raises(ValueError, match="No camera devices"):
        pick_source("camera")


def test_pick_source_no_match_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_catalog(
        monkeypatch,
        [
            {"kind": "microphone", "name": "Built-in", "index": 0,
             "platform": "darwin", "driver": "avfoundation"},
        ],
    )
    with pytest.raises(ValueError, match="No microphone matches"):
        pick_source("microphone", name_substring="USB")


# ---------------------------------------------------------------------------
# ffmpeg_input_args — per-OS argv builder
# ---------------------------------------------------------------------------


def test_ffmpeg_input_args_avfoundation_camera() -> None:
    src: ch.Source = {
        "kind": "camera", "name": "FaceTime HD Camera", "index": 0,
        "platform": "darwin", "driver": "avfoundation",
    }
    assert ffmpeg_input_args(src) == ["-f", "avfoundation", "-i", "0:none"]


def test_ffmpeg_input_args_avfoundation_mic() -> None:
    src: ch.Source = {
        "kind": "microphone", "name": "Built-in Microphone", "index": 1,
        "platform": "darwin", "driver": "avfoundation",
    }
    assert ffmpeg_input_args(src) == ["-f", "avfoundation", "-i", "none:1"]


def test_ffmpeg_input_args_v4l2() -> None:
    src: ch.Source = {
        "kind": "camera", "name": "/dev/video0", "index": 0,
        "platform": "linux", "driver": "v4l2",
    }
    assert ffmpeg_input_args(src) == ["-f", "v4l2", "-i", "/dev/video0"]


def test_ffmpeg_input_args_dshow_camera() -> None:
    src: ch.Source = {
        "kind": "camera", "name": "Integrated Webcam", "index": 0,
        "platform": "windows", "driver": "dshow",
    }
    assert ffmpeg_input_args(src) == ["-f", "dshow", "-i", "video=Integrated Webcam"]


def test_ffmpeg_input_args_dshow_mic() -> None:
    src: ch.Source = {
        "kind": "microphone", "name": "Microphone Array (Realtek)", "index": 0,
        "platform": "windows", "driver": "dshow",
    }
    assert ffmpeg_input_args(src) == ["-f", "dshow", "-i", "audio=Microphone Array (Realtek)"]


def test_ffmpeg_input_args_pulse() -> None:
    src: ch.Source = {
        "kind": "microphone", "name": "alsa_input.usb_mic", "index": 0,
        "platform": "linux", "driver": "pulse",
    }
    assert ffmpeg_input_args(src) == ["-f", "pulse", "-i", "alsa_input.usb_mic"]


def test_ffmpeg_input_args_unknown_driver_raises() -> None:
    src: ch.Source = {
        "kind": "camera", "name": "weird", "index": 0,
        "platform": "weird", "driver": "made-up",
    }
    with pytest.raises(ValueError, match="Unsupported source driver"):
        ffmpeg_input_args(src)


# ---------------------------------------------------------------------------
# iter_camera_frames — input validation (no real device required)
# ---------------------------------------------------------------------------


def test_iter_camera_frames_rejects_mic_source() -> None:
    mic_src: ch.Source = {
        "kind": "microphone", "name": "Built-in", "index": 0,
        "platform": "darwin", "driver": "avfoundation",
    }
    it: Iterator = ch.iter_camera_frames(mic_src, output_width=640, output_height=360)
    with pytest.raises(ValueError, match="camera source"):
        next(it)


def test_iter_camera_frames_requires_known_resolution() -> None:
    cam_src: ch.Source = {
        "kind": "camera", "name": "x", "index": 0,
        "platform": "darwin", "driver": "avfoundation",
    }
    it: Iterator = ch.iter_camera_frames(cam_src)  # no resolution at all
    with pytest.raises(ValueError, match="requires"):
        next(it)


# ---------------------------------------------------------------------------
# iter_mic_audio — input validation (no real device required)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_iter_mic_audio_rejects_camera_source() -> None:
    cam_src: ch.Source = {
        "kind": "camera", "name": "x", "index": 0,
        "platform": "darwin", "driver": "avfoundation",
    }
    with pytest.raises(ValueError, match="microphone source"):
        async for _ in ch.iter_mic_audio(cam_src):
            pass


# Note: we don't ship pytest-asyncio in dev deps yet — guard the async
# test so the suite still passes without that plugin installed. The
# sync tests above already cover the bulk of v0.1.0.
def _has_asyncio_plugin() -> bool:
    try:
        import pytest_asyncio  # noqa: F401
    except ImportError:
        return False
    return True


if not _has_asyncio_plugin():
    # Replace the marker with a skip so plain pytest still passes.
    test_iter_mic_audio_rejects_camera_source = pytest.mark.skip(  # type: ignore[assignment]
        reason="pytest-asyncio not installed; covered manually in EXAMPLES.md"
    )(test_iter_mic_audio_rejects_camera_source)
