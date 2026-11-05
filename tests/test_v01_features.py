"""
Smoke tests for v0.1.0 — pick_source + ffmpeg_input_args + iterator
contracts (no real device required).

These tests don't ask for real hardware: they monkeypatch
``list_sources`` to seed the catalog, exercise the selector and
per-OS argv builder, and verify that the iterator entry points
exist with the right shape.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

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
            {
                "kind": "camera",
                "name": "FaceTime HD Camera",
                "index": 0,
                "platform": "darwin",
                "driver": "avfoundation",
            },
            {
                "kind": "camera",
                "name": "iPhone Camera",
                "index": 1,
                "platform": "darwin",
                "driver": "avfoundation",
            },
        ],
    )
    cam = pick_source("camera")
    assert cam["name"] == "FaceTime HD Camera"


def test_pick_source_name_substring_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_catalog(
        monkeypatch,
        [
            {
                "kind": "microphone",
                "name": "Built-in Microphone",
                "index": 0,
                "platform": "darwin",
                "driver": "avfoundation",
            },
            {
                "kind": "microphone",
                "name": "BlackHole 16ch",
                "index": 1,
                "platform": "darwin",
                "driver": "avfoundation",
            },
        ],
    )
    mic = pick_source("microphone", name_substring="blackhole")
    assert mic["name"] == "BlackHole 16ch"


def test_pick_source_by_index(monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_catalog(
        monkeypatch,
        [
            {"kind": "camera", "name": "A", "index": 0, "platform": "linux", "driver": "v4l2"},
            {"kind": "camera", "name": "B", "index": 1, "platform": "linux", "driver": "v4l2"},
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
            {
                "kind": "microphone",
                "name": "Built-in",
                "index": 0,
                "platform": "darwin",
                "driver": "avfoundation",
            },
        ],
    )
    with pytest.raises(ValueError, match="No microphone matches"):
        pick_source("microphone", name_substring="USB")


# ---------------------------------------------------------------------------
# ffmpeg_input_args — per-OS argv builder
# ---------------------------------------------------------------------------


def test_ffmpeg_input_args_avfoundation_camera() -> None:
    src: ch.Source = {
        "kind": "camera",
        "name": "FaceTime HD Camera",
        "index": 0,
        "platform": "darwin",
        "driver": "avfoundation",
    }
    assert ffmpeg_input_args(src) == ["-f", "avfoundation", "-i", "0:none"]


def test_ffmpeg_input_args_avfoundation_mic() -> None:
    src: ch.Source = {
        "kind": "microphone",
        "name": "Built-in Microphone",
        "index": 1,
        "platform": "darwin",
        "driver": "avfoundation",
    }
    assert ffmpeg_input_args(src) == ["-f", "avfoundation", "-i", "none:1"]


def test_ffmpeg_input_args_v4l2() -> None:
    src: ch.Source = {
        "kind": "camera",
        "name": "/dev/video0",
        "index": 0,
        "platform": "linux",
        "driver": "v4l2",
    }
    assert ffmpeg_input_args(src) == ["-f", "v4l2", "-i", "/dev/video0"]


def test_ffmpeg_input_args_dshow_camera() -> None:
    src: ch.Source = {
        "kind": "camera",
        "name": "Integrated Webcam",
        "index": 0,
        "platform": "windows",
        "driver": "dshow",
    }
    assert ffmpeg_input_args(src) == ["-f", "dshow", "-i", "video=Integrated Webcam"]


def test_ffmpeg_input_args_dshow_mic() -> None:
    src: ch.Source = {
        "kind": "microphone",
        "name": "Microphone Array (Realtek)",
        "index": 0,
        "platform": "windows",
        "driver": "dshow",
    }
    assert ffmpeg_input_args(src) == ["-f", "dshow", "-i", "audio=Microphone Array (Realtek)"]


def test_ffmpeg_input_args_pulse() -> None:
    src: ch.Source = {
        "kind": "microphone",
        "name": "alsa_input.usb_mic",
        "index": 0,
        "platform": "linux",
        "driver": "pulse",
    }
    assert ffmpeg_input_args(src) == ["-f", "pulse", "-i", "alsa_input.usb_mic"]


def test_ffmpeg_input_args_unknown_driver_raises() -> None:
    src: ch.Source = {
        "kind": "camera",
        "name": "weird",
        "index": 0,
        "platform": "weird",
        "driver": "made-up",
    }
    with pytest.raises(ValueError, match="Unsupported source driver"):
        ffmpeg_input_args(src)


# ---------------------------------------------------------------------------
# iter_camera_frames — input validation (no real device required)
# ---------------------------------------------------------------------------


def test_iter_camera_frames_rejects_mic_source() -> None:
    mic_src: ch.Source = {
        "kind": "microphone",
        "name": "Built-in",
        "index": 0,
        "platform": "darwin",
        "driver": "avfoundation",
    }
    it: Iterator = ch.iter_camera_frames(mic_src, output_width=640, output_height=360)
    with pytest.raises(ValueError, match="camera source"):
        next(it)


def test_iter_camera_frames_requires_known_resolution() -> None:
    cam_src: ch.Source = {
        "kind": "camera",
        "name": "x",
        "index": 0,
        "platform": "darwin",
        "driver": "avfoundation",
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
        "kind": "camera",
        "name": "x",
        "index": 0,
        "platform": "darwin",
        "driver": "avfoundation",
    }
    with pytest.raises(ValueError, match="microphone source"):
        async for _ in ch.iter_mic_audio(cam_src):
            pass


class _FakeFailedStdout:
    """Mimics ffmpeg exiting immediately: the very first read gets nothing."""

    async def readexactly(self, n: int) -> bytes:
        raise asyncio.IncompleteReadError(partial=b"", expected=n)


class _FakeStderr:
    def __init__(self, message: bytes) -> None:
        self._message = message

    async def read(self) -> bytes:
        # A real pipe returns b"" on every read once drained -- only the
        # first call should see the message.
        msg, self._message = self._message, b""
        return msg


class _FakeFailedProc:
    """Mimics an ffmpeg process that exits (permission/device error) before
    producing a single frame -- no real subprocess involved."""

    def __init__(self) -> None:
        self.stdout = _FakeFailedStdout()
        self.stderr = _FakeStderr(b"Input/output error: mic permission denied")
        self.returncode: int | None = 1

    async def wait(self) -> int:
        return self.returncode

    def terminate(self) -> None:
        pass

    def kill(self) -> None:
        pass


@pytest.mark.asyncio
async def test_iter_mic_audio_raises_when_ffmpeg_exits_with_zero_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A stalled/denied device used to look identical to "recorded nothing
    # yet, stream just ended" -- an empty async generator, no exception --
    # instead of surfacing the real cause. Must now raise RuntimeError with
    # ffmpeg's stderr, the same contract iter_camera_frames already has.
    mic_src: ch.Source = {
        "kind": "microphone",
        "name": "x",
        "index": 0,
        "platform": "darwin",
        "driver": "avfoundation",
    }

    async def _fake_create_subprocess_exec(*_a: object, **_kw: object) -> _FakeFailedProc:
        return _FakeFailedProc()

    monkeypatch.setattr(
        "capture_helper.mic.asyncio.create_subprocess_exec", _fake_create_subprocess_exec
    )

    with pytest.raises(RuntimeError, match="permission denied"):
        async for _ in ch.iter_mic_audio(mic_src):
            pass


# ---------------------------------------------------------------------------
# iter_mic_audio — channel layout and teardown
# ---------------------------------------------------------------------------


_MIC: ch.Source = {
    "kind": "microphone",
    "name": "x",
    "index": 0,
    "platform": "darwin",
    "driver": "avfoundation",
}


def test_mic_cmd_pins_the_channel_count_the_reader_assumes() -> None:
    """``to_mono=False`` is read as stereo, so ffmpeg must be told to emit stereo.

    Without ``-ac 2`` a mono built-in mic reached the reader as one channel
    and was sliced as two: half-length frames of interleaved garbage, with
    ``t_abs_s`` advancing at half the real rate.
    """
    from capture_helper.mic import _build_ffmpeg_cmd

    mono = _build_ffmpeg_cmd(_MIC, target_sample_rate=16000, to_mono=True)
    stereo = _build_ffmpeg_cmd(_MIC, target_sample_rate=16000, to_mono=False)
    assert mono[mono.index("-ac") + 1] == "1"
    assert stereo[stereo.index("-ac") + 1] == "2"
    # -ac is an output option: before -i it would apply to nothing.
    assert stereo.index("-ac") > stereo.index("-i")


@pytest.mark.asyncio
async def test_closing_a_mic_stream_behind_a_full_pipe_returns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A consumer that fell behind must still be able to close the stream.

    The unread stdout pipe fills, asyncio pauses it and never sees its EOF,
    and ``proc.wait()`` used to block forever, even after the kill. ffmpeg
    traps SIGTERM, hence the child ignoring it.
    """
    import sys

    import capture_helper.mic as mic_mod

    script = (
        "import signal, sys, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "sys.stdout.buffer.write(b'\\x00' * 4_000_000)\n"
        "sys.stdout.flush()\n"
        "time.sleep(60)\n"
    )
    monkeypatch.setattr(
        mic_mod, "_build_ffmpeg_cmd", lambda *a, **k: [sys.executable, "-c", script]
    )

    agen = ch.iter_mic_audio(_MIC)
    await agen.__anext__()
    await asyncio.sleep(0.3)  # let the child fill the pipe
    await asyncio.wait_for(agen.aclose(), timeout=10.0)


# ---------------------------------------------------------------------------
# ffmpeg dying mid-stream — the iterators must say the stream stopped short
# ---------------------------------------------------------------------------


def _child(script: str) -> list[str]:
    import sys

    return [sys.executable, "-c", script]


_TWO_MIC_FRAMES_THEN_FAIL = (
    "import sys\n"
    "sys.stdout.buffer.write(b'\\x00' * (320 * 4 * 2))\n"
    "sys.stdout.flush()\n"
    "sys.stderr.write('device unplugged')\n"
    "sys.exit(1)\n"
)


@pytest.mark.asyncio
async def test_mic_stream_raises_when_ffmpeg_fails_after_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A device lost mid-recording must not look like a complete recording."""
    import capture_helper.mic as mic_mod

    monkeypatch.setattr(
        mic_mod, "_build_ffmpeg_cmd", lambda *a, **k: _child(_TWO_MIC_FRAMES_THEN_FAIL)
    )
    got = 0
    with pytest.raises(RuntimeError, match="device unplugged"):
        async for _ in ch.iter_mic_audio(_MIC):
            got += 1
    assert got == 2


@pytest.mark.asyncio
async def test_mic_stream_ends_quietly_when_ffmpeg_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import capture_helper.mic as mic_mod

    ok = _TWO_MIC_FRAMES_THEN_FAIL.replace("sys.exit(1)", "sys.exit(0)")
    monkeypatch.setattr(mic_mod, "_build_ffmpeg_cmd", lambda *a, **k: _child(ok))
    frames = [f async for f in ch.iter_mic_audio(_MIC)]
    assert len(frames) == 2


@pytest.mark.asyncio
async def test_mic_stream_stopped_by_consumer_never_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import capture_helper.mic as mic_mod

    monkeypatch.setattr(
        mic_mod, "_build_ffmpeg_cmd", lambda *a, **k: _child(_TWO_MIC_FRAMES_THEN_FAIL)
    )
    frames = [f async for f in ch.iter_mic_audio(_MIC, max_frames=1)]
    assert len(frames) == 1


_CAM: ch.Source = {
    "kind": "camera",
    "name": "x",
    "index": 0,
    "platform": "darwin",
    "driver": "avfoundation",
}

_TWO_CAM_FRAMES_THEN_FAIL = (
    "import sys\n"
    "sys.stdout.buffer.write(b'\\x00' * (4 * 2 * 3 * 2))\n"
    "sys.stdout.flush()\n"
    "sys.stderr.write('camera unplugged')\n"
    "sys.exit(1)\n"
)


def test_camera_stream_raises_when_ffmpeg_fails_after_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import capture_helper.camera as cam_mod

    monkeypatch.setattr(
        cam_mod, "_build_ffmpeg_cmd", lambda *a, **k: _child(_TWO_CAM_FRAMES_THEN_FAIL)
    )
    got = 0
    with pytest.raises(RuntimeError, match="camera unplugged"):
        for _ in ch.iter_camera_frames(_CAM, output_width=4, output_height=2):
            got += 1
    assert got == 2


def test_camera_stream_ends_quietly_when_ffmpeg_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import capture_helper.camera as cam_mod

    ok = _TWO_CAM_FRAMES_THEN_FAIL.replace("sys.exit(1)", "sys.exit(0)")
    monkeypatch.setattr(cam_mod, "_build_ffmpeg_cmd", lambda *a, **k: _child(ok))
    frames = list(ch.iter_camera_frames(_CAM, output_width=4, output_height=2))
    assert len(frames) == 2


def test_camera_stream_stopped_by_consumer_never_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import capture_helper.camera as cam_mod

    monkeypatch.setattr(
        cam_mod, "_build_ffmpeg_cmd", lambda *a, **k: _child(_TWO_CAM_FRAMES_THEN_FAIL)
    )
    frames = list(ch.iter_camera_frames(_CAM, output_width=4, output_height=2, max_frames=1))
    assert len(frames) == 1
