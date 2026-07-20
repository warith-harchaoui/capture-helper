"""
Capture Helper
==============

Local-first, library-shaped **camera / microphone capture layer** for the
AI Helpers stack. It ships the **INPUT layer**: cross-platform device
enumeration + selection (cameras / microphones) and a pair of iterators
that bridge those devices to the rest of the suite's contracts — plus a
**live multi-source scene configurator** (a browser GUI served by the
FastAPI app) that turns a visual layout of live sources into a reusable
JSON scene artifact the CLI / API can replay headless.

The capture layer
------------------
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

The scene configurator (additive, does not touch the iterators)
---------------------------------------------------------------
- :class:`Scene` / :class:`SceneSource` — a named canvas of placed
  sources with per-source capture parameters.
- :func:`new_scene` / :func:`add_source` — build a scene in code.
- :func:`save_scene` / :func:`load_scene` / :func:`validate_scene` —
  persist and reload the visual design as JSON.
- :func:`resolve_scene_sources` / :func:`scene_from_available_devices` —
  map a scene onto the current machine's live devices.
- :func:`snapshot_jpeg` / :func:`iter_camera_jpeg` / :func:`mic_level` —
  live-preview primitives powering the browser GUI (camera JPEG / MJPEG,
  microphone level meters).

This is an early-stage project. The public iterator contracts above are
stable; the scene / preview surface is new and additive.

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
    # scene / config model (scene configurator backend)
    "Scene",
    "SceneSource",
    "ResolvedSceneSource",
    "new_scene",
    "add_source",
    "validate_scene",
    "save_scene",
    "load_scene",
    "resolve_scene_sources",
    "scene_from_available_devices",
    "SCENE_FORMAT_VERSION",
    "SCENE_SUFFIX",
    # live-preview primitives (GUI)
    "frame_to_jpeg",
    "snapshot_jpeg",
    "iter_camera_jpeg",
    "mic_level",
    "rms_dbfs",
]

from .camera import iter_camera_frames
from .mic import MicFrame, iter_mic_audio
from .preview import (
    frame_to_jpeg,
    iter_camera_jpeg,
    mic_level,
    rms_dbfs,
    snapshot_jpeg,
)
from .scene import (
    SCENE_FORMAT_VERSION,
    SCENE_SUFFIX,
    ResolvedSceneSource,
    Scene,
    SceneSource,
    add_source,
    load_scene,
    new_scene,
    resolve_scene_sources,
    save_scene,
    scene_from_available_devices,
    validate_scene,
)
from .sources import Source, SourceKind, ffmpeg_input_args, list_sources, pick_source
