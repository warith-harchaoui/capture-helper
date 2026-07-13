"""
Capture Helper — click-based command-line interface.

Twin of :mod:`capture_helper.cli_argparse`: same public surface
(identical subcommand names, identical flag semantics), but implemented
with :mod:`click` so users who already have a click-native shell setup
(bash / zsh completion via ``click.shell_completion``, colored ``--help``,
nested command groups) can plug it in without friction. Installed as
the ``capture-helper-click`` entry point in ``pyproject.toml``.

Design notes
------------
- Subcommands mirror ``capture-helper`` (the argparse twin) so both
  CLIs can be introspected identically by higher layers (FastAPI, MCP).
- Flags reuse the argparse names (``--kind`` / ``--name`` / …) rather
  than the more idiomatic click positional style — consistency across
  the two CLIs beats micro-idiomaticity here.
- Errors from the library propagate unchanged; click handles the
  formatting.

Usage Example
-------------
>>> #   capture-helper-click list-sources
>>> #   capture-helper-click pick-source --kind camera --name FaceTime
>>> #   capture-helper-click input-args --kind microphone --index 0
>>> #   capture-helper-click capture-camera --output-dir frames/ \\
>>> #       --output-width 640 --output-height 360 --max-frames 30
>>> #   capture-helper-click capture-mic --output mic.wav --seconds 3

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import asyncio
import json
import sys
import wave
from pathlib import Path

import numpy as np

try:
    import click
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The click CLI requires the [cli] extra. "
        "Install with: pip install 'capture-helper[cli]'"
    ) from exc

# Same underlying functions as the argparse twin — one source of truth.
from . import (
    ffmpeg_input_args,
    iter_camera_frames,
    iter_mic_audio,
    list_sources,
    pick_source,
)


# ---------------------------------------------------------------------------
# Top-level group
#
# ``invoke_without_command=False`` forces the user to name a subcommand;
# ``context_settings`` widens the help output so long option lists stay
# readable on modern terminals.
# ---------------------------------------------------------------------------


@click.group(
    context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 100},
)
@click.version_option(package_name="capture-helper", prog_name="capture-helper-click")
def cli() -> None:
    """Capture Helper — click twin of the argparse CLI. Same subcommands."""
    # Nothing to do at the group level — every subcommand carries its
    # own arguments and side effects.


# ---------------------------------------------------------------------------
# list-sources
# ---------------------------------------------------------------------------


@cli.command("list-sources")
@click.option(
    "--kind",
    type=click.Choice(["camera", "microphone"]),
    default=None,
    help="Filter to one kind; omit to list both.",
)
def list_sources_cmd(kind: str | None) -> None:
    """Enumerate available capture devices (JSON output)."""
    click.echo(json.dumps(list_sources(kind), indent=2))


# ---------------------------------------------------------------------------
# pick-source
# ---------------------------------------------------------------------------


@cli.command("pick-source")
@click.option("--kind", type=click.Choice(["camera", "microphone"]), required=True)
@click.option("--name", default=None, help="Case-insensitive substring on the device name.")
@click.option("--index", type=int, default=None, help="Exact index match.")
def pick_source_cmd(kind: str, name: str | None, index: int | None) -> None:
    """Pick a single capture device by kind / name / index (JSON output)."""
    src = pick_source(kind, name_substring=name, index=index)
    click.echo(json.dumps(src, indent=2))


# ---------------------------------------------------------------------------
# input-args
# ---------------------------------------------------------------------------


@cli.command("input-args")
@click.option("--kind", type=click.Choice(["camera", "microphone"]), required=True)
@click.option("--name", default=None, help="Case-insensitive substring on the device name.")
@click.option("--index", type=int, default=None, help="Exact index match.")
def input_args_cmd(kind: str, name: str | None, index: int | None) -> None:
    """Print the ffmpeg ``-f DRIVER -i SPEC`` argv fragment for a resolved device."""
    src = pick_source(kind, name_substring=name, index=index)
    click.echo(" ".join(ffmpeg_input_args(src)))


# ---------------------------------------------------------------------------
# capture-camera
# ---------------------------------------------------------------------------


@cli.command("capture-camera")
@click.option("--name", default=None, help="Case-insensitive substring on the device name.")
@click.option("--index", type=int, default=None, help="Exact index match.")
@click.option("--output-dir", required=True, type=click.Path(),
              help="Folder that receives the captured frames.")
@click.option("--width", type=int, default=None, help="Capture-side width (before decode).")
@click.option("--height", type=int, default=None, help="Capture-side height (before decode).")
@click.option("--fps", type=float, default=None, help="Capture-side frame rate.")
@click.option("--output-width", type=int, default=None,
              help="Post-decode output width (scale-fit-and-pad).")
@click.option("--output-height", type=int, default=None,
              help="Post-decode output height (scale-fit-and-pad).")
@click.option("--pad-color", default="black", show_default=True,
              help="Pad colour when scale-fit-and-pad applies.")
@click.option("--max-frames", type=int, default=30, show_default=True,
              help="Stop after this many frames.")
def capture_camera_cmd(
    name: str | None,
    index: int | None,
    output_dir: str,
    width: int | None,
    height: int | None,
    fps: float | None,
    output_width: int | None,
    output_height: int | None,
    pad_color: str,
    max_frames: int,
) -> None:
    """Capture N frames from a camera and write raw bgr24 files to ``--output-dir``."""
    src = pick_source("camera", name_substring=name, index=index)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
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
        p = out_dir / f"frame_{i:06d}.bgr24"
        p.write_bytes(frame.tobytes())
        click.echo(str(p))


# ---------------------------------------------------------------------------
# capture-mic
# ---------------------------------------------------------------------------


async def _mic_to_wav_async(
    src: dict,
    out_path: Path,
    *,
    target_sample_rate: int,
    to_mono: bool,
    frame_ms: int,
    max_frames: int | None,
) -> int:
    """Same helper as the argparse twin — collect PCM, write WAV."""
    # Buffer int16 samples in memory. Fine for a few seconds; longer
    # recordings should use the library directly.
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
        click.echo("capture-helper: no audio captured (permission denied?)", err=True)
        return 2

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
    click.echo(str(out_path))
    return 0


@cli.command("capture-mic")
@click.option("--name", default=None, help="Case-insensitive substring on the device name.")
@click.option("--index", type=int, default=None, help="Exact index match.")
@click.option("--output", required=True, type=click.Path(), help="Output WAV path.")
@click.option("--seconds", type=float, default=3.0, show_default=True,
              help="Recording duration in seconds.")
@click.option("--sample-rate", type=int, default=16000, show_default=True,
              help="Target sample rate in Hz.")
@click.option("--frame-ms", type=int, default=20, show_default=True,
              help="Frame duration in ms.")
@click.option("--mono/--no-mono", default=True, show_default=True,
              help="Downmix to mono or preserve source channels.")
def capture_mic_cmd(
    name: str | None,
    index: int | None,
    output: str,
    seconds: float,
    sample_rate: int,
    frame_ms: int,
    mono: bool,
) -> None:
    """Record N seconds of microphone audio to a WAV file."""
    frames_per_sec = max(1, 1000 // frame_ms)
    max_frames = int(seconds * frames_per_sec)
    src = pick_source("microphone", name_substring=name, index=index)
    rc = asyncio.run(
        _mic_to_wav_async(
            src,
            Path(output),
            target_sample_rate=sample_rate,
            to_mono=mono,
            frame_ms=frame_ms,
            max_frames=max_frames,
        )
    )
    if rc != 0:
        sys.exit(rc)


if __name__ == "__main__":  # pragma: no cover
    cli()
