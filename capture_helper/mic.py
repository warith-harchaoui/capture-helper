"""
capture_helper.mic
==================

Live microphone-PCM async iterator that bridges
:func:`capture_helper.list_sources` output with the **same PCM-frame
contract** that :func:`podcast_helper.extract_audio_stream` uses for
URL-based audio. The intent is: *if you can drop a podcast URL into an
ASR / VAD pipeline, you can drop a live mic in*.

Implementation
--------------
- Shells out to ``ffmpeg`` with the right per-OS input driver
  (``-f avfoundation`` / ``-f pulse`` / ``-f alsa`` / ``-f dshow``)
  built by :func:`capture_helper.sources.ffmpeg_input_args`.
- Asks ffmpeg to resample to ``target_sample_rate`` and downmix to mono
  (or preserve the source channel count) and emit raw ``f32le`` PCM
  to stdout. We read fixed-size byte blocks and yield
  :class:`MicFrame`-typed dicts.
- Async generator — matches
  :func:`podcast_helper.extract_audio_stream`'s shape so consumers can
  ``async for frame in ...`` regardless of whether the source is a URL
  or a local microphone.

Usage example
-------------
>>> import asyncio, capture_helper as ch
>>> async def main():
...     mic = ch.pick_source("microphone")
...     async for frame in ch.iter_mic_audio(mic, target_sample_rate=16000,
...                                          to_mono=True, frame_ms=20):
...         # frame["pcm"]: np.float32, shape (320,) for 20ms @ 16kHz mono
...         await asr.feed(frame["pcm"])
>>> asyncio.run(main())

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Optional, TypedDict

import numpy as np
import os_helper as osh
from numpy.typing import NDArray

from .sources import Source, ffmpeg_input_args


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class MicFrame(TypedDict):
    """
    One PCM frame from a live microphone, in absolute capture time.

    Structurally identical to :class:`podcast_helper.streaming.PcmFrame`
    so downstream consumers (VAD, ASR, dB-meter, …) don't have to
    branch on the source type.

    Keys
    ----
    t_abs_s : float
        Seconds since ffmpeg latched onto the device. Monotonic.
    pcm : NDArray[np.float32]
        Audio samples in ``[-1.0, 1.0]``, ``float32``.

        - Shape ``(n_samples,)`` when ``to_mono=True`` (default).
        - Shape ``(n_samples, n_channels)`` when ``to_mono=False`` and
          the source has more than one channel.
    voiced : bool | None
        Always ``None`` here — VAD downstream fills it in if used.
    """

    t_abs_s: float
    pcm: NDArray[np.float32]
    voiced: Optional[bool]


# ---------------------------------------------------------------------------
# Internal — ffmpeg command builder
# ---------------------------------------------------------------------------


def _build_ffmpeg_cmd(
    source: Source,
    *,
    target_sample_rate: int,
    to_mono: bool,
) -> list[str]:
    """
    Assemble the ffmpeg command line for a live microphone capture.

    Output is raw 32-bit float little-endian PCM on stdout — same shape
    as :func:`podcast_helper.extract_audio_stream`'s ffmpeg pipeline so
    the downstream byte-reading loop is the same.

    Parameters
    ----------
    source : Source
        Microphone source dict.
    target_sample_rate : int
        Exact output sample rate in Hz. Triggers ffmpeg's
        libswresample anti-aliasing low-pass at the new Nyquist when
        the source rate differs.
    to_mono : bool
        Downmix to one channel (ffmpeg's standard L+R matrix) or
        preserve the source channel count verbatim.

    Returns
    -------
    list[str]
        Full argv ready for :func:`asyncio.create_subprocess_exec`.
    """
    # Suite-wide ffmpeg shape — headless, quiet, single-shot.
    cmd: list[str] = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin"]

    # Per-OS input driver + device spec.
    cmd += ffmpeg_input_args(source)

    # Resample to the requested rate. Default libswresample (polyphase
    # with anti-aliasing low-pass) is the right choice for ASR / VAD /
    # ML — same logic as podcast_helper.
    cmd += ["-ar", str(target_sample_rate)]

    # Channel handling. Downmix to mono is a deterministic, standard
    # ffmpeg matrix. Preserving native channels lets stereo / spatial
    # mics through unchanged.
    if to_mono:
        cmd += ["-ac", "1"]

    # Output: raw 32-bit float little-endian PCM to stdout.
    cmd += ["-f", "f32le", "-"]
    return cmd


# ---------------------------------------------------------------------------
# Public — async live-mic iterator
# ---------------------------------------------------------------------------


async def iter_mic_audio(
    source: Source,
    *,
    target_sample_rate: int = 16000,
    to_mono: bool = True,
    frame_ms: int = 20,
    max_frames: int | None = None,
) -> AsyncIterator[MicFrame]:
    """
    Yield PCM frames from a live microphone.

    Parameters
    ----------
    source : Source
        Device dict returned by :func:`pick_source` /
        :func:`list_sources`. Its ``kind`` must be ``"microphone"``.
    target_sample_rate : int, default 16000
        Exact output sample rate in Hz. ffmpeg resamples via
        libswresample with an anti-aliasing low-pass at the new
        Nyquist — Shannon-correct and more than enough for ASR / VAD /
        ML pipelines.
    to_mono : bool, default True
        - True: ffmpeg standard downmix to one channel;
          ``pcm.shape == (n_samples,)``.
        - False: preserve the source's native channel count;
          ``pcm.shape == (n_samples, n_channels)`` (only set when the
          source actually has more than one channel).
    frame_ms : int, default 20
        Frame duration in milliseconds. ``20`` matches Silero VAD's
        native frame size, avoiding a downstream re-buffer.
    max_frames : int, optional
        Stop after yielding this many frames. ``None`` (default) =
        unbounded — runs until the source disconnects or the consumer
        breaks the ``async for``.

    Yields
    ------
    MicFrame
        Successive PCM frames in absolute capture time.

    Raises
    ------
    ValueError
        If ``source["kind"]`` isn't ``"microphone"``, or if
        ``frame_ms`` / ``target_sample_rate`` is non-positive.
    FileNotFoundError
        Raised by ffmpeg / asyncio if ``ffmpeg`` isn't on PATH.

    Examples
    --------
    >>> import asyncio, capture_helper as ch
    >>> async def main():
    ...     mic = ch.pick_source("microphone")
    ...     async for frame in ch.iter_mic_audio(mic):
    ...         # frame["pcm"]: np.float32 (320,) for 20ms @ 16kHz mono
    ...         pass
    >>> asyncio.run(main())
    """
    # Cheap validation up front — surfacing a clear error here beats a
    # cryptic ffmpeg failure (or a silent garbage-data stream) later.
    if source["kind"] != "microphone":
        raise ValueError(
            f"iter_mic_audio expects a microphone source, got kind={source['kind']!r}"
        )
    if frame_ms <= 0:
        raise ValueError(f"frame_ms must be > 0, got {frame_ms}")
    if target_sample_rate <= 0:
        raise ValueError(f"target_sample_rate must be > 0, got {target_sample_rate}")

    cmd = _build_ffmpeg_cmd(
        source,
        target_sample_rate=target_sample_rate,
        to_mono=to_mono,
    )
    osh.debug("capture-helper: mic ffmpeg cmd: %s", " ".join(cmd))

    # Channel count: known to be 1 in to_mono mode. When preserving
    # native channels, we DON'T ffprobe the live device (probing a busy
    # device is fragile across OSes — and in many cases the very same
    # device can only be opened once at a time). Instead we let the
    # caller pass ``to_mono=True`` (the common case for ASR / VAD), and
    # for ``to_mono=False`` we assume stereo (2). A future v0.2.0 may
    # cache a probe result during list_sources.
    n_channels: int = 1 if to_mono else 2
    bytes_per_sample = 4  # float32 LE
    samples_per_frame = max(1, (target_sample_rate * frame_ms) // 1000)
    bytes_per_frame = samples_per_frame * n_channels * bytes_per_sample

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert proc.stdout is not None
    assert proc.stderr is not None

    t_abs_s = 0.0
    seconds_per_frame = samples_per_frame / target_sample_rate
    yielded = 0

    try:
        while True:
            try:
                raw = await proc.stdout.readexactly(bytes_per_frame)
            except asyncio.IncompleteReadError as exc:
                # Short read at end-of-stream. Pad the trailing partial
                # frame with silence so the caller sees a clean
                # fixed-size final frame — same convention as
                # podcast_helper.
                if exc.partial:
                    pad = bytes_per_frame - len(exc.partial)
                    raw = exc.partial + (b"\x00" * pad)
                else:
                    break

            arr = np.frombuffer(raw, dtype=np.float32).copy()
            if n_channels > 1:
                arr = arr.reshape((-1, n_channels))

            yield {"t_abs_s": t_abs_s, "pcm": arr, "voiced": None}
            t_abs_s += seconds_per_frame
            yielded += 1

            if max_frames is not None and yielded >= max_frames:
                break
    finally:
        # Always tear down the subprocess — leaking ffmpeg keeps the
        # mic locked for the rest of the OS session.
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
        err = (await proc.stderr.read()).decode("utf-8", errors="replace").strip()
        if err and proc.returncode not in (0, None):
            logging.warning("capture-helper mic ffmpeg stderr: %s", err)
