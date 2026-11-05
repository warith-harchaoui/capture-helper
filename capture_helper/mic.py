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
  (or deliver exactly two channels) and emit raw ``f32le`` PCM
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
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TypedDict

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
        - Shape ``(n_samples, 2)`` when ``to_mono=False``: a mono
          device is duplicated onto both channels, an interface with
          more than two is downmixed to stereo.
    voiced : bool | None
        Always ``None`` here — VAD downstream fills it in if used.
    """

    t_abs_s: float
    pcm: NDArray[np.float32]
    voiced: bool | None


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
        Downmix to one channel (ffmpeg's standard L+R matrix), or
        deliver exactly two channels (see :func:`iter_mic_audio`).

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
    # ffmpeg matrix. Otherwise the output is pinned to two channels: the
    # reader cannot probe a live device for its channel count, so it slices
    # the pipe as stereo, and a bare "native" output from a mono built-in mic
    # would be read as stereo frames of half the duration -- garbage samples
    # on a clock running at half speed.
    cmd += ["-ac", "1" if to_mono else "2"]

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
        - False: two channels, ``pcm.shape == (n_samples, 2)``. A live
          device cannot be probed for its channel count, so the output is
          pinned to stereo: a mono device is duplicated onto both
          channels, a larger interface is downmixed.
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
    RuntimeError
        If ffmpeg exits before the first frame (permission denied, device
        busy), or exits non-zero later (device unplugged, driver error).
        Frames already yielded stay valid; the exception says the stream
        stopped short. Stopping early yourself (``max_frames``, ``break``)
        never raises.

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
        raise ValueError(f"iter_mic_audio expects a microphone source, got kind={source['kind']!r}")
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

    # Channel count: 1 in to_mono mode, else 2. We DON'T ffprobe the live
    # device (probing a busy device is fragile across OSes, and many devices
    # can only be opened once at a time), so _build_ffmpeg_cmd pins the
    # output to the count read here with ``-ac``.
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
                elif yielded == 0:
                    # ffmpeg exited before a single frame was produced.
                    # Silently returning an empty stream here would look
                    # identical to "the mic recorded nothing yet" to a
                    # caller, hiding the real cause (permission denied,
                    # device busy) — surface it the same way
                    # iter_camera_frames does for the analogous case.
                    await proc.wait()
                    stderr_bytes = await proc.stderr.read()
                    err = stderr_bytes.decode("utf-8", errors="replace").strip()
                    raise RuntimeError(
                        "ffmpeg exited before yielding a frame — common causes: "
                        "OS microphone permission denied, device busy in another "
                        "app, or unsupported capture mode. ffmpeg stderr: " + (err or "(empty)")
                    ) from exc
                else:
                    # stdout closed on its own. A clean end only if ffmpeg
                    # says so: a device unplugged or a driver error also
                    # closes it, and the caller must not take a truncated
                    # stream for a complete one.
                    await proc.wait()
                    if proc.returncode != 0:
                        stderr_bytes = await proc.stderr.read()
                        err = stderr_bytes.decode("utf-8", errors="replace").strip()
                        raise RuntimeError(
                            f"ffmpeg exited with code {proc.returncode} after "
                            f"{t_abs_s:.2f}s of audio: {err or '(no stderr)'}"
                        ) from exc
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
            # Keep reading stdout while ffmpeg dies. A consumer that fell
            # behind leaves the pipe full; asyncio then pauses it, never sees
            # its EOF, and proc.wait() (which waits for the pipes as well as
            # the exit) blocks forever, even after the kill.
            async def _discard_stdout() -> None:
                assert proc.stdout is not None
                while await proc.stdout.read(1 << 16):
                    pass

            discard_task = asyncio.create_task(_discard_stdout())
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                proc.kill()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    osh.warning("capture-helper: mic ffmpeg (pid %s) survived a kill", proc.pid)
            discard_task.cancel()
        err = (await proc.stderr.read()).decode("utf-8", errors="replace").strip()
        if err and proc.returncode not in (0, None):
            osh.warning("capture-helper mic ffmpeg stderr: %s", err)
