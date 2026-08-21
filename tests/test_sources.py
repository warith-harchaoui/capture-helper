"""Smoke tests for ``capture_helper.sources``.

The actual device enumeration is platform-dependent; we test the
parsers on captured fixtures rather than asking for real hardware.
"""

from capture_helper.sources import (
    _parse_avfoundation_devices,
    _parse_dshow_devices,
    list_sources,
)

_AVFOUNDATION_SAMPLE = """\
[AVFoundation indev @ 0x12a304880] AVFoundation video devices:
[AVFoundation indev @ 0x12a304880] [0] FaceTime HD Camera
[AVFoundation indev @ 0x12a304880] [1] Capture screen 0
[AVFoundation indev @ 0x12a304880] AVFoundation audio devices:
[AVFoundation indev @ 0x12a304880] [0] Built-in Microphone
[AVFoundation indev @ 0x12a304880] [1] External USB Mic
"""


_DSHOW_SAMPLE = """\
[dshow @ 0000023f3a8e0c00] DirectShow video devices (some may be both video and audio devices)
[dshow @ 0000023f3a8e0c00]  "Integrated Webcam"
[dshow @ 0000023f3a8e0c00] DirectShow audio devices
[dshow @ 0000023f3a8e0c00]  "Microphone Array (Realtek)"
[dshow @ 0000023f3a8e0c00]  "External USB Mic"
"""

# Real ffmpeg builds print an indented "Alternative name" line right after
# each device's own quoted name (a machine-readable device path). It must
# NOT be counted as a second device; see the regression test below.
_DSHOW_SAMPLE_WITH_ALT_NAMES = """\
[dshow @ 0000023f3a8e0c00] DirectShow video devices (some may be both video and audio devices)
[dshow @ 0000023f3a8e0c00]  "Integrated Webcam"
[dshow @ 0000023f3a8e0c00]     Alternative name "@device_pnp_\\\\?\\usb#vid_04f2&pid_b57f"
[dshow @ 0000023f3a8e0c00] DirectShow audio devices
[dshow @ 0000023f3a8e0c00]  "Microphone Array (Realtek)"
[dshow @ 0000023f3a8e0c00]     Alternative name "@device_cm_{33D9A762-90C8}"
[dshow @ 0000023f3a8e0c00]  "External USB Mic"
[dshow @ 0000023f3a8e0c00]     Alternative name "@device_cm_{4A2B1C0D-11AA}"
"""


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def test_parse_avfoundation_extracts_camera_and_mic():
    sources = _parse_avfoundation_devices(_AVFOUNDATION_SAMPLE)
    cams = [s for s in sources if s["kind"] == "camera"]
    mics = [s for s in sources if s["kind"] == "microphone"]
    assert len(cams) == 1
    assert cams[0]["name"] == "FaceTime HD Camera"
    assert cams[0]["index"] == 0
    assert cams[0]["driver"] == "avfoundation"
    assert [m["name"] for m in mics] == ["Built-in Microphone", "External USB Mic"]


def test_parse_avfoundation_skips_screen_capture():
    """Screen capture is parked for v0.2.0 and should not leak through as camera."""
    sources = _parse_avfoundation_devices(_AVFOUNDATION_SAMPLE)
    assert not any("screen" in s["name"].lower() for s in sources)


def test_parse_dshow_extracts_both():
    sources = _parse_dshow_devices(_DSHOW_SAMPLE)
    cams = [s for s in sources if s["kind"] == "camera"]
    mics = [s for s in sources if s["kind"] == "microphone"]
    assert [c["name"] for c in cams] == ["Integrated Webcam"]
    assert [m["name"] for m in mics] == ["Microphone Array (Realtek)", "External USB Mic"]
    assert mics[0]["driver"] == "dshow"


def test_parse_dshow_skips_alternative_name_lines():
    """Regression test: "Alternative name" is device metadata, not a device.

    Before the fix, each "Alternative name \"...\"" line was mistaken for a
    quoted device name, doubling the device count and shifting every later
    index, so ``pick_source(..., index=N)`` would resolve to the wrong
    camera/microphone on Windows.
    """
    sources = _parse_dshow_devices(_DSHOW_SAMPLE_WITH_ALT_NAMES)
    cams = [s for s in sources if s["kind"] == "camera"]
    mics = [s for s in sources if s["kind"] == "microphone"]
    assert [c["name"] for c in cams] == ["Integrated Webcam"]
    assert [m["name"] for m in mics] == ["Microphone Array (Realtek)", "External USB Mic"]
    # Indices must stay dense/correct, not shifted by the bogus entries.
    assert [m["index"] for m in mics] == [0, 1]


def test_parse_garbage_returns_empty():
    assert _parse_avfoundation_devices("") == []
    assert _parse_avfoundation_devices("totally unrelated stderr") == []
    assert _parse_dshow_devices("") == []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def test_list_sources_returns_list_never_raises():
    """Smoke test — on any platform, the call must not raise."""
    assert isinstance(list_sources(), list)
    assert isinstance(list_sources("camera"), list)
    assert isinstance(list_sources("microphone"), list)


def test_list_sources_filter_kind():
    cams = list_sources("camera")
    mics = list_sources("microphone")
    for s in cams:
        assert s["kind"] == "camera"
    for s in mics:
        assert s["kind"] == "microphone"
