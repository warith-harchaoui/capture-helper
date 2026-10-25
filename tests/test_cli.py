"""
Smoke tests for the command line — one door now, built with click.

These exercise the CLI *parsing* layer without touching real capture
devices: the goal is to catch regressions in the entry point (flag
names, subcommand names, dispatch wiring) without pulling in ffmpeg or
the OS permission stack.

There used to be two CLIs — argparse plus an optional click twin — with
most scenarios written twice so the pair could be checked for drift. The
twin is the only CLI now, so each scenario is asserted once. The three
cases that existed *only* on the argparse side (raw-PCM `stream-mic`, its
exit-2 path, and the scene save/validate round-trip) were carried over
rather than dropped: they were the real coverage, not the duplication.

Usage Example
-------------
>>> #   pytest tests/test_cli.py

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import json
import sys

import pytest
from click.testing import CliRunner

from capture_helper import cli as cli_mod

# Every verb the CLI must expose. Kept as a module-level constant so one
# quietly disappearing fails here rather than in a user's shell.
SUBCOMMANDS = [
    "list-sources",
    "pick-source",
    "input-args",
    "capture-camera",
    "capture-mic",
    "stream-mic",
    "scene-auto",
    "scene-validate",
    "scene-show",
]


def test_group_has_expected_subcommands():
    """The click group exposes every verb the library promises."""
    assert set(SUBCOMMANDS).issubset(set(cli_mod.cli.commands.keys()))


def test_help_exits_zero():
    """``capture-helper --help`` exits 0 and names itself."""
    result = CliRunner().invoke(cli_mod.cli, ["--help"])
    assert result.exit_code == 0
    assert "capture helper" in result.output.lower()


@pytest.mark.parametrize("sub", SUBCOMMANDS)
def test_subcommand_help_exits_zero(sub):
    """Every subcommand's ``--help`` exits 0 — no wiring bug."""
    result = CliRunner().invoke(cli_mod.cli, [sub, "--help"])
    assert result.exit_code == 0


def test_list_sources_runs_and_emits_json():
    """``capture-helper list-sources`` emits a JSON array."""
    result = CliRunner().invoke(cli_mod.cli, ["list-sources"])
    assert result.exit_code == 0
    assert isinstance(json.loads(result.output), list)


def test_main_library_error_prints_clean_message_not_traceback(monkeypatch, capsys):
    """A library ``ValueError`` becomes one stderr line + exit 1, not a traceback.

    Drives ``main()`` rather than ``cli`` through ``CliRunner``, because
    ``main()`` is the wrapper that does the translating — the console script
    used to point at the bare ``cli`` group, which has no such handling.
    """

    def _raise(*_a, **_kw):
        raise ValueError("No camera devices available")

    monkeypatch.setattr(cli_mod, "pick_source", _raise)
    monkeypatch.setattr(sys, "argv", ["capture-helper", "pick-source", "--kind", "camera"])
    with pytest.raises(SystemExit) as excinfo:
        cli_mod.main()
    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert captured.err.strip() == "Error: No camera devices available"
    assert "Traceback" not in captured.err


# ---------------------------------------------------------------------------
# stream-mic — no real device: monkeypatch iter_mic_audio with a fake
# async generator and assert the raw PCM bytes on stdout match exactly.
# ---------------------------------------------------------------------------


def _fake_frames(pcm_arrays):
    """Build an async generator mimicking ``iter_mic_audio``'s frame shape."""

    async def _gen(*_args, **_kwargs):
        t = 0.0
        for pcm in pcm_arrays:
            yield {"t_abs_s": t, "pcm": pcm, "voiced": None}
            t += 0.02

    return _gen


def _run_argv(monkeypatch, argv):
    """Drive ``main()`` the way the console script does, and return its code.

    ``CliRunner`` captures stdout as text, which would corrupt the raw PCM
    these two tests assert on, so they go through ``main()`` with a patched
    ``sys.argv`` and read the real binary stream back with ``capsysbinary``.
    """
    monkeypatch.setattr(sys, "argv", ["capture-helper", *argv])
    try:
        cli_mod.main()
    except SystemExit as exc:  # click and the subcommands both exit this way
        return int(exc.code or 0)
    return 0


def test_stream_mic_writes_raw_pcm_to_stdout(monkeypatch, capsysbinary):
    """``stream-mic`` writes exactly the concatenated raw f32le bytes.

    No WAV header, no text interleaved on stdout — a consumer reads the pipe
    as a byte stream, so one stray print would corrupt the audio.
    """
    import numpy as np

    frames = [
        np.array([0.1, -0.2, 0.3], dtype=np.float32),
        np.array([0.4, 0.5], dtype=np.float32),
    ]
    monkeypatch.setattr(cli_mod, "iter_mic_audio", _fake_frames(frames))
    monkeypatch.setattr(cli_mod, "pick_source", lambda *a, **k: {"kind": "microphone", "index": 0})

    assert _run_argv(monkeypatch, ["stream-mic", "--seconds", "1"]) == 0
    out = capsysbinary.readouterr().out
    assert out == np.concatenate(frames).astype(np.float32).tobytes()


def test_stream_mic_no_frames_exits_2(monkeypatch, capsysbinary):
    """No captured audio (e.g. a permission denial) exits 2 rather than crashing."""
    monkeypatch.setattr(cli_mod, "iter_mic_audio", _fake_frames([]))
    monkeypatch.setattr(cli_mod, "pick_source", lambda *a, **k: {"kind": "microphone", "index": 0})

    assert _run_argv(monkeypatch, ["stream-mic", "--seconds", "1"]) == 2


# ---------------------------------------------------------------------------
# Scene subcommands — the artifact save / validate / show flow (hardware-free)
# ---------------------------------------------------------------------------


def test_scene_auto_and_validate_round_trip(tmp_path):
    """``scene-auto --output`` writes a file that ``scene-validate`` accepts."""
    runner = CliRunner()
    out = tmp_path / "auto.scene.json"
    # Auto-populate to a file (empty of sources on a headless CI runner).
    written = runner.invoke(cli_mod.cli, ["scene-auto", "--name", "ci", "--output", str(out)])
    assert written.exit_code == 0, written.output
    assert out.exists()
    # Validation of the just-written artifact must pass.
    checked = runner.invoke(cli_mod.cli, ["scene-validate", "--input", str(out)])
    assert checked.exit_code == 0, checked.output
    assert "valid scene" in checked.output


def test_scene_auto_emits_valid_json():
    """``scene-auto`` in stdout mode emits a well-formed scene."""
    result = CliRunner().invoke(cli_mod.cli, ["scene-auto", "--name", "ci"])
    assert result.exit_code == 0
    scene = json.loads(result.output)
    assert scene["name"] == "ci"
    assert isinstance(scene["sources"], list)
