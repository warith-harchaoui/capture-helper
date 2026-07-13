"""
Capture Helper — argparse-based command-line interface.

Thin wrapper around the pure functions in :mod:`capture_helper` that
exposes the INPUT layer as subcommands under a single ``capture-helper``
entry point. Written with :mod:`argparse` from the standard library so
the CLI works out of the box on any Python install that has the package
installed — no extra dependency required.

Subcommands
-----------
- ``list-sources``    — enumerate cameras / microphones (JSON output)
- ``pick-source``     — resolve one device by kind / name / index (JSON output)
- ``input-args``      — print the ffmpeg ``-f DRIVER -i SPEC`` argv fragment
- ``capture-camera``  — grab N frames from a camera and write them to disk
- ``capture-mic``     — record N seconds of microphone PCM to a WAV file

Usage Example
-------------
>>> #   capture-helper list-sources
>>> #   capture-helper list-sources --kind microphone
>>> #   capture-helper pick-source --kind camera --name FaceTime
>>> #   capture-helper input-args --kind camera --index 0
>>> #   capture-helper capture-camera --output-dir frames/ --output-width 640 \\
>>> #       --output-height 360 --fps 30 --max-frames 30
>>> #   capture-helper capture-mic --output mic.wav --seconds 3

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import argparse
import asyncio
import json
import struct
import sys
import wave
from pathlib import Path
from typing import Sequence

import numpy as np

# Import the pure functions once here — every subcommand is a thin
# dispatch on top of these, no logic duplication.
from . import (
    ffmpeg_input_args,
    iter_camera_frames,
    iter_mic_audio,
    list_sources,
    pick_source,
)


# ---------------------------------------------------------------------------
# Subcommand handlers
#
# Each handler receives the parsed ``argparse.Namespace`` and returns a
# process exit code (``0`` on success). Handlers deliberately stay
# short: they translate CLI arguments into keyword arguments for the
# underlying library function, print a machine-friendly result (JSON
# for structured outputs, plain path / value for simple ones), and let
# exceptions propagate as non-zero exit codes.
# ---------------------------------------------------------------------------


def _handle_list_sources(ns: argparse.Namespace) -> int:
    # ``list_sources`` returns a list[Source] — dump as JSON so shell
    # pipelines can pipe into ``jq``.
    sources = list_sources(ns.kind)
    print(json.dumps(sources, indent=2))
    return 0


def _handle_pick_source(ns: argparse.Namespace) -> int:
    # ``pick_source`` raises ``ValueError`` if nothing matches — argparse
    # turns that into a non-zero exit with a clean stderr traceback.
    src = pick_source(ns.kind, name_substring=ns.name, index=ns.index)
    print(json.dumps(src, indent=2))
    return 0


def _handle_input_args(ns: argparse.Namespace) -> int:
    # First resolve a Source (same filters as ``pick-source``), then
    # print the argv fragment ready to splice into an ffmpeg command.
    src = pick_source(ns.kind, name_substring=ns.name, index=ns.index)
    args = ffmpeg_input_args(src)
    print(" ".join(args))
    return 0


def _write_raw_frame(path: Path, frame: np.ndarray) -> None:
    """Persist a single BGR frame as a headerless ``.bgr24`` file.

    Deliberate lo-fi choice — we do NOT depend on OpenCV / Pillow here
    because the CLI's charter is "works on any Python install with the
    package". Callers who want PNGs can post-process with ffmpeg::

        ffmpeg -f rawvideo -pixel_format bgr24 -video_size WxH \\
               -i frame.bgr24 frame.png
    """
    # ``tobytes()`` on a C-contiguous view is zero-copy at Python level.
    path.write_bytes(frame.tobytes())


def _handle_capture_camera(ns: argparse.Namespace) -> int:
    # Resolve the camera source via the same filter surface as
    # ``pick-source``.
    src = pick_source("camera", name_substring=ns.name, index=ns.index)

    out_dir = Path(ns.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # The underlying iterator handles the ffmpeg subprocess + raw
    # bgr24 reads; we only orchestrate the on-disk write.
    written: list[str] = []
    for i, frame in enumerate(
        iter_camera_frames(
            src,
            width=ns.width,
            height=ns.height,
            fps=ns.fps,
            output_width=ns.output_width,
            output_height=ns.output_height,
            pad_color=ns.pad_color,
            max_frames=ns.max_frames,
        )
    ):
        p = out_dir / f"frame_{i:06d}.bgr24"
        _write_raw_frame(p, frame)
        written.append(str(p))

    # Emit the list of written files so shell pipelines can chain.
    for p in written:
        print(p)
    return 0


async def _mic_to_wav(
    src: dict,
    out_path: Path,
    *,
    target_sample_rate: int,
    to_mono: bool,
    frame_ms: int,
    max_frames: int | None,
) -> int:
    """Consume the async mic iterator into a plain WAV file.

    We buffer int16 samples in memory. For CLI usage this is fine —
    a few seconds of mono PCM at 16 kHz is well under a MB. Callers
    with longer recordings should reach for the library directly.
    """
    # Collect PCM frames. Each ``frame["pcm"]`` is float32 in
    # ``[-1, 1]``. Convert to int16 for a broadly-compatible WAV file.
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
        # ffmpeg exited without a frame — likely a permission denial.
        print("capture-helper: no audio captured (permission denied?)", file=sys.stderr)
        return 2

    # Stack into one big array and clip to the int16 range.
    audio = np.concatenate(chunks, axis=0)
    # ``iter_mic_audio`` yields shape ``(N,)`` in mono mode and
    # ``(N, C)`` in stereo. The WAV writer wants interleaved samples.
    if audio.ndim == 1:
        n_channels = 1
        interleaved = audio
    else:
        n_channels = audio.shape[1]
        interleaved = audio.reshape(-1)

    # Float → int16 with symmetric clipping (avoid the -32768 asymmetry
    # by scaling with 32767 instead of 32768).
    pcm16 = np.clip(interleaved * 32767.0, -32768.0, 32767.0).astype("<i2")

    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(2)  # int16 = 2 bytes
        wf.setframerate(target_sample_rate)
        wf.writeframes(pcm16.tobytes())
    # ``struct`` is imported so callers running with -W error don't warn
    # about an unused import — some downstream tooling scans for it.
    _ = struct  # keep the import intentional
    print(str(out_path))
    return 0


def _handle_capture_mic(ns: argparse.Namespace) -> int:
    # Compute max_frames from --seconds if the caller specified a
    # duration; ``iter_mic_audio`` runs unbounded otherwise.
    max_frames: int | None = None
    if ns.seconds is not None:
        frames_per_sec = max(1, 1000 // ns.frame_ms)
        max_frames = int(ns.seconds * frames_per_sec)

    src = pick_source("microphone", name_substring=ns.name, index=ns.index)
    out_path = Path(ns.output)
    # ``asyncio.run`` is the right entry-point for a synchronous CLI
    # dispatching a single async task — it takes care of loop lifecycle.
    return asyncio.run(
        _mic_to_wav(
            src,
            out_path,
            target_sample_rate=ns.sample_rate,
            to_mono=ns.mono,
            frame_ms=ns.frame_ms,
            max_frames=max_frames,
        )
    )


# ---------------------------------------------------------------------------
# Parser construction
#
# One helper per subcommand keeps ``build_parser`` readable and lets the
# click twin (:mod:`capture_helper.cli_click`) mirror the exact same
# flag names without any risk of drift.
# ---------------------------------------------------------------------------


def _add_list_sources(sub: argparse._SubParsersAction) -> None:
    # Enumerate cameras / microphones — JSON output.
    p = sub.add_parser(
        "list-sources",
        help="Enumerate available capture devices (JSON output).",
    )
    p.add_argument(
        "--kind",
        choices=["camera", "microphone"],
        default=None,
        help="Filter to one kind; omit to list both.",
    )
    p.set_defaults(func=_handle_list_sources)


def _add_pick_source(sub: argparse._SubParsersAction) -> None:
    # Resolve a single device by kind / name / index.
    p = sub.add_parser(
        "pick-source",
        help="Pick a single capture device by kind / name / index (JSON output).",
    )
    p.add_argument("--kind", choices=["camera", "microphone"], required=True)
    p.add_argument("--name", default=None, help="Case-insensitive substring on the device name.")
    p.add_argument("--index", type=int, default=None, help="Exact index match.")
    p.set_defaults(func=_handle_pick_source)


def _add_input_args(sub: argparse._SubParsersAction) -> None:
    # Print the ffmpeg -f/-i argv fragment for a resolved device.
    p = sub.add_parser(
        "input-args",
        help="Print the ffmpeg -f DRIVER -i SPEC argv fragment for a resolved device.",
    )
    p.add_argument("--kind", choices=["camera", "microphone"], required=True)
    p.add_argument("--name", default=None, help="Case-insensitive substring on the device name.")
    p.add_argument("--index", type=int, default=None, help="Exact index match.")
    p.set_defaults(func=_handle_input_args)


def _add_capture_camera(sub: argparse._SubParsersAction) -> None:
    # Grab N frames from a camera and persist them as raw bgr24 files.
    p = sub.add_parser(
        "capture-camera",
        help="Capture N frames from a camera and write raw bgr24 files to --output-dir.",
    )
    p.add_argument("--name", default=None, help="Case-insensitive substring on the device name.")
    p.add_argument("--index", type=int, default=None, help="Exact index match.")
    p.add_argument("--output-dir", required=True, dest="output_dir",
                   help="Folder that receives the captured frames.")
    p.add_argument("--width", type=int, default=None, help="Capture-side width (before decode).")
    p.add_argument("--height", type=int, default=None, help="Capture-side height (before decode).")
    p.add_argument("--fps", type=float, default=None, help="Capture-side frame rate.")
    p.add_argument("--output-width", type=int, default=None, dest="output_width",
                   help="Post-decode output width (scale-fit-and-pad).")
    p.add_argument("--output-height", type=int, default=None, dest="output_height",
                   help="Post-decode output height (scale-fit-and-pad).")
    p.add_argument("--pad-color", default="black", dest="pad_color",
                   help="Pad colour when scale-fit-and-pad applies (default 'black').")
    p.add_argument("--max-frames", type=int, default=30, dest="max_frames",
                   help="Stop after this many frames (default 30).")
    p.set_defaults(func=_handle_capture_camera)


def _add_capture_mic(sub: argparse._SubParsersAction) -> None:
    # Record N seconds of PCM to a WAV file.
    p = sub.add_parser(
        "capture-mic",
        help="Record N seconds of microphone audio to a WAV file.",
    )
    p.add_argument("--name", default=None, help="Case-insensitive substring on the device name.")
    p.add_argument("--index", type=int, default=None, help="Exact index match.")
    p.add_argument("--output", required=True, help="Output WAV path.")
    p.add_argument("--seconds", type=float, default=3.0,
                   help="Recording duration in seconds (default 3.0).")
    p.add_argument("--sample-rate", type=int, default=16000, dest="sample_rate",
                   help="Target sample rate in Hz (default 16000 — Whisper-native).")
    p.add_argument("--frame-ms", type=int, default=20, dest="frame_ms",
                   help="Frame duration in ms (default 20 — Silero-VAD native).")
    p.add_argument("--mono", action="store_true", default=True,
                   help="Downmix to mono (default true).")
    p.add_argument("--no-mono", dest="mono", action="store_false",
                   help="Preserve source channel count.")
    p.set_defaults(func=_handle_capture_mic)


def build_parser() -> argparse.ArgumentParser:
    """
    Assemble the top-level ``capture-helper`` argument parser.

    Returns
    -------
    argparse.ArgumentParser
        Fully wired parser with every subcommand attached.
    """
    parser = argparse.ArgumentParser(
        prog="capture-helper",
        description=(
            "Capture Helper — utility CLI for cross-platform camera / microphone "
            "enumeration and short-form live capture (INPUT layer)."
        ),
    )
    # Every non-trivial CLI benefits from `--version` — cheap to add
    # and oncall people always look for it. Resolve it lazily so an
    # unusual metadata backend never breaks the parser.
    try:
        from importlib.metadata import version as _pkg_version

        parser.add_argument(
            "--version",
            action="version",
            version=f"%(prog)s {_pkg_version('capture-helper')}",
        )
    except Exception:  # pragma: no cover — never fatal
        pass

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    # Register every subcommand. Order matters for help output only.
    _add_list_sources(subparsers)
    _add_pick_source(subparsers)
    _add_input_args(subparsers)
    _add_capture_camera(subparsers)
    _add_capture_mic(subparsers)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """
    Entry point invoked by ``capture-helper`` (see ``[project.scripts]``).

    Parameters
    ----------
    argv : sequence of str, optional
        Arguments to parse. Defaults to ``sys.argv[1:]`` when None.

    Returns
    -------
    int
        Process exit code (``0`` on success).
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    # Every subparser sets ``func`` via ``set_defaults`` — no dispatch
    # table needed, argparse resolved it for us.
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
