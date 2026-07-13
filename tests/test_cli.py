"""
Smoke tests for the argparse and click CLIs.

These tests exercise the CLI *parsing* layer without touching real
capture devices — the goal is to prevent regressions in the entry
points (flag names, subcommand names, dispatch wiring) without
pulling in ffmpeg or the OS permission stack.

Usage Example
-------------
>>> #   pytest tests/test_cli.py

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import json

import pytest

# The click CLI needs the ``click`` runtime dep, which lives in the
# ``[cli]`` optional extra. Skip cleanly if it is not installed.
click = pytest.importorskip("click")

from click.testing import CliRunner  # noqa: E402


# ---------------------------------------------------------------------------
# argparse CLI
# ---------------------------------------------------------------------------


def test_argparse_parser_builds_without_error():
    """Building the parser should never fail (imports, subcommand wiring)."""
    from capture_helper.cli_argparse import build_parser

    parser = build_parser()
    # A parser with at least one subcommand exposes them via _subparsers.
    # We assert on the expected list of subcommand names to catch drift.
    subparsers_action = next(
        a for a in parser._actions if a.__class__.__name__ == "_SubParsersAction"
    )
    expected = {"list-sources", "pick-source", "input-args", "capture-camera", "capture-mic"}
    assert expected.issubset(set(subparsers_action.choices.keys()))


def test_argparse_help_exits_zero(capsys):
    """``capture-helper --help`` should exit with code 0 and print usage."""
    from capture_helper.cli_argparse import main

    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "capture-helper" in captured.out.lower()


@pytest.mark.parametrize(
    "sub",
    ["list-sources", "pick-source", "input-args", "capture-camera", "capture-mic"],
)
def test_argparse_subcommand_help_exits_zero(sub):
    """Every subcommand's ``--help`` should exit 0 (no wiring bug)."""
    from capture_helper.cli_argparse import main

    with pytest.raises(SystemExit) as exc:
        main([sub, "--help"])
    assert exc.value.code == 0


def test_argparse_list_sources_runs_and_emits_json(capsys):
    """``capture-helper list-sources`` should print a JSON array — smoke only.

    On CI we don't know what devices exist; ``list_sources`` is
    guaranteed to return ``[]`` rather than raise on unsupported
    platforms. Either way stdout must parse as a list.
    """
    from capture_helper.cli_argparse import main

    rc = main(["list-sources"])
    assert rc == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert isinstance(parsed, list)


# ---------------------------------------------------------------------------
# click CLI
# ---------------------------------------------------------------------------


def test_click_group_has_expected_subcommands():
    """The click group must expose the same subcommands as the argparse CLI."""
    from capture_helper.cli_click import cli

    expected = {"list-sources", "pick-source", "input-args", "capture-camera", "capture-mic"}
    assert expected.issubset(set(cli.commands.keys()))


def test_click_help_exits_zero():
    """``capture-helper-click --help`` should exit 0."""
    from capture_helper.cli_click import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "capture helper" in result.output.lower()


@pytest.mark.parametrize(
    "sub",
    ["list-sources", "pick-source", "input-args", "capture-camera", "capture-mic"],
)
def test_click_subcommand_help_exits_zero(sub):
    """Every click subcommand's ``--help`` should exit 0."""
    from capture_helper.cli_click import cli

    runner = CliRunner()
    result = runner.invoke(cli, [sub, "--help"])
    assert result.exit_code == 0


def test_click_list_sources_runs_and_emits_json():
    """``capture-helper-click list-sources`` should emit a JSON array."""
    from capture_helper.cli_click import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["list-sources"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert isinstance(parsed, list)
