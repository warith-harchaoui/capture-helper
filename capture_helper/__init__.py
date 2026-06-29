"""
Capture Helper
==============

OBS-inspired (no GUI) **capture + process + publish** library for the
AI Helpers stack. v0.0.1 is a scaffold: only the public types and
device enumeration are exposed; the iter / mix / publish layers land
in subsequent releases.

What it will be
---------------
The same philosophy as OBS but as a Python library:

- **Inputs**: cross-platform camera / microphone / screen / window /
  application-audio sources.
- **Process**: composable filter chains (noise gate, gain, chroma key,
  scale, color correct) + multi-source mixing.
- **Publish**: RTMP to YouTube Live / Twitch, HLS, Icecast (live
  podcasts), virtual webcam / mic outputs, OBS WebSocket bidirectional
  control.

What it ships *today* (v0.0.1)
------------------------------
- :class:`SourceKind` literal
- :class:`Source` typed dict
- :func:`list_sources` — best-effort cross-platform device enumeration
  via ``ffmpeg -list_devices`` (avfoundation / v4l2 / dshow).
  Returns `[]` rather than raising on unsupported platforms.

See the README for the per-version roadmap.

Author:
- Warith HARCHAOUI (https://linkedin.com/in/warith-harchaoui)
"""

__all__ = [
    "SourceKind",
    "Source",
    "list_sources",
]

from .sources import Source, SourceKind, list_sources
