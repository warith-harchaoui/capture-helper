"""
Capture Helper
==============

OBS-inspired (no GUI) **capture + process + publish** library for the
AI Helpers stack. v0.1.0 ships the **INPUT layer**: cross-platform
device enumeration + selection (cameras / microphones) and a pair of
iterators that bridge those devices to the rest of the suite's
contracts.

What ships in v0.1.0
--------------------
- :class:`SourceKind` — literal ``"camera"`` | ``"microphone"``.
- :class:`Source` — typed dict describing one device.
- :class:`MicFrame` — typed dict for one PCM frame (mirrors
  :class:`podcast_helper.streaming.PcmFrame`).
- :func:`list_sources` — best-effort cross-platform device enumeration
  via ``ffmpeg -list_devices`` (avfoundation / v4l2 / dshow / pulse /
  alsa). Returns ``[]`` rather than raising on unsupported platforms.
- :func:`pick_source` — pick the first device of a given kind matching
  optional ``name_substring`` / ``index`` filters.
- :func:`iter_camera_frames` — synchronous generator yielding
  ``(H, W, 3)`` BGR uint8 numpy arrays — same shape and dtype as
  :func:`video_helper.extract_frames`.
- :func:`iter_mic_audio` — async generator yielding
  :class:`MicFrame` — same shape as
  :func:`podcast_helper.extract_audio_stream`.

What lands next
---------------
See :doc:`README` roadmap. v0.2.0 brings screen / window capture and a
basic filter chain; v0.3.0 brings multi-source mixing; v0.4.0 brings
RTMP / HLS / Icecast publish.

Usage example
-------------
>>> import asyncio, capture_helper as ch
>>> cam = ch.pick_source("camera")
>>> for frame in ch.iter_camera_frames(cam, output_width=640, output_height=360,
...                                    fps=30, max_frames=300):
...     # frame.shape == (360, 640, 3), dtype uint8, BGR.
...     do_something(frame)
>>>
>>> async def listen():
...     mic = ch.pick_source("microphone")
...     async for f in ch.iter_mic_audio(mic, target_sample_rate=16000, frame_ms=20):
...         # f["pcm"].shape == (320,) — 20ms @ 16kHz mono.
...         await asr.feed(f["pcm"])
>>> asyncio.run(listen())

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

# Package-level attribution — kept here so tooling that reads
# ``capture_helper.__author__`` gets the canonical value. Email lives
# ONLY here (never in module-level docstrings) to keep source files
# scrapeable without leaking the mailbox to search engines.
__author__ = "Warith Harchaoui, Ph.D."
__email__ = "warithmetics@deraison.ai"

__all__ = [
    # types
    "SourceKind",
    "Source",
    "MicFrame",
    # device enumeration + selection
    "list_sources",
    "pick_source",
    # low-level helper exposed because some callers want to splice the
    # per-OS ffmpeg input args into their own pipelines.
    "ffmpeg_input_args",
    # live capture iterators
    "iter_camera_frames",
    "iter_mic_audio",
]

from .camera import iter_camera_frames
from .mic import MicFrame, iter_mic_audio
from .sources import Source, SourceKind, ffmpeg_input_args, list_sources, pick_source
