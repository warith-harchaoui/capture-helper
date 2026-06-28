"""
capture_helper.sources
======================

Cross-platform capture-device enumeration via ``ffmpeg``'s
``-list_devices`` mode. We shell out and parse stderr because there is
no clean cross-platform Python API for this — the per-OS alternatives
(``pyobjc-AVFoundation`` on macOS, ``v4l2-python`` on Linux,
``pywin32 / dshow`` on Windows) are heavier, harder to install, and
less consistent than just asking ffmpeg.

Limitations
-----------
- ``ffmpeg -list_devices`` is **stderr-based** and the line format
  drifts between ffmpeg versions and platforms. We parse defensively
  and return ``[]`` rather than raising when the format surprises us.
- Returns devices with the names ffmpeg reports, **including any
  trailing platform-specific bracketed metadata**.
- Screen / window sources are NOT exposed in v0.0.1 — they need a
  different ffmpeg input format per OS (``avfoundation`` screen index
  on macOS, ``x11grab`` / ``wayland`` on Linux, ``gdigrab`` on Windows)
  and the abstraction is best designed once we have a real iter
  function consuming them. v0.2.0 target.

Author:
- Warith HARCHAOUI (https://harchaoui.org/warith)
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from typing import List, Literal, TypedDict


SourceKind = Literal["camera", "microphone"]


class Source(TypedDict):
    """One capture device, normalised across platforms.

    Keys
    ----
    kind : ``"camera"`` | ``"microphone"``
        Audio / video distinction.
    name : str
        Human-readable name as reported by the OS driver. Use this when
        passing to a future ``iter_camera_frames`` / ``iter_mic_audio``
        — the per-OS ffmpeg input string is built internally.
    index : int
        Numeric device index in ffmpeg's listing (0-based). Some OS
        backends only accept the index; others accept name OR index.
    platform : str
        ``"darwin"`` / ``"linux"`` / ``"windows"`` — useful for callers
        that branch on the underlying driver (avfoundation / v4l2 /
        dshow / pulse).
    driver : str
        ffmpeg input format flag — ``"avfoundation"`` / ``"v4l2"`` /
        ``"dshow"`` / ``"pulse"`` / ``"alsa"``.
    """

    kind: SourceKind
    name: str
    index: int
    platform: str
    driver: str


# ---------------------------------------------------------------------------
# Per-platform enumeration
# ---------------------------------------------------------------------------


def _run_ffmpeg_list_devices(driver: str) -> str:
    """Shell out to ffmpeg and return stderr (where -list_devices writes)."""
    if shutil.which("ffmpeg") is None:
        return ""
    try:
        # -f <driver> -list_devices true -i ""  — exits non-zero by design.
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-f", driver, "-list_devices", "true", "-i", ""],
            capture_output=True, text=True, check=False, timeout=10,
        )
        # The device list comes on stderr; some ffmpeg builds also dump it on stdout.
        return (proc.stderr or "") + "\n" + (proc.stdout or "")
    except (subprocess.TimeoutExpired, OSError):
        return ""


def _parse_avfoundation_devices(stderr: str) -> List[Source]:
    """Parse macOS ffmpeg avfoundation listing.

    Format::

        [AVFoundation indev @ 0x...] AVFoundation video devices:
        [AVFoundation indev @ 0x...] [0] FaceTime HD Camera
        [AVFoundation indev @ 0x...] [1] Capture screen 0
        [AVFoundation indev @ 0x...] AVFoundation audio devices:
        [AVFoundation indev @ 0x...] [0] Built-in Microphone
    """
    out: List[Source] = []
    current_kind: SourceKind | None = None
    for line in stderr.splitlines():
        s = line.strip()
        if "AVFoundation video devices" in s:
            current_kind = "camera"
            continue
        if "AVFoundation audio devices" in s:
            current_kind = "microphone"
            continue
        if current_kind is None:
            continue
        # "[AVFoundation indev @ 0x...] [N] Name"
        if "]" not in s:
            continue
        # split off the [N] index and the name
        try:
            after_marker = s.split("]", 1)[1].strip()
            if not after_marker.startswith("["):
                continue
            idx_str, name = after_marker.split("]", 1)
            idx = int(idx_str.lstrip("[").strip())
            nm = name.strip()
        except (ValueError, IndexError):
            continue
        # macOS lumps "Capture screen N" under video devices — skip for now
        # (screen capture lands in v0.2.0 with its own abstraction).
        if current_kind == "camera" and nm.lower().startswith("capture screen"):
            continue
        out.append({
            "kind": current_kind, "name": nm, "index": idx,
            "platform": "darwin", "driver": "avfoundation",
        })
    return out


def _parse_dshow_devices(stderr: str) -> List[Source]:
    """Parse Windows ffmpeg DirectShow listing (dshow).

    Format::

        [dshow @ ...] DirectShow video devices
        [dshow @ ...]  "Integrated Webcam"
        [dshow @ ...] DirectShow audio devices
        [dshow @ ...]  "Microphone Array (Realtek...)"
    """
    out: List[Source] = []
    current_kind: SourceKind | None = None
    index_per_kind: dict = {"camera": 0, "microphone": 0}
    for line in stderr.splitlines():
        s = line.strip()
        if "DirectShow video devices" in s:
            current_kind = "camera"
            continue
        if "DirectShow audio devices" in s:
            current_kind = "microphone"
            continue
        if current_kind is None:
            continue
        if "\"" not in s:
            continue
        try:
            nm = s.split("\"", 2)[1]
        except IndexError:
            continue
        if not nm.strip():
            continue
        out.append({
            "kind": current_kind, "name": nm,
            "index": index_per_kind[current_kind],
            "platform": "windows", "driver": "dshow",
        })
        index_per_kind[current_kind] += 1
    return out


def _list_linux_devices() -> List[Source]:
    """Linux: cameras via /dev/video*, mics via pactl / arecord (best-effort)."""
    out: List[Source] = []
    # Cameras: /dev/video0, /dev/video1, ... (v4l2)
    import glob
    for idx, dev in enumerate(sorted(glob.glob("/dev/video*"))):
        out.append({
            "kind": "camera", "name": dev, "index": idx,
            "platform": "linux", "driver": "v4l2",
        })
    # Microphones: prefer pulse, fall back to alsa.
    if shutil.which("pactl") is not None:
        try:
            proc = subprocess.run(
                ["pactl", "list", "short", "sources"],
                capture_output=True, text=True, check=False, timeout=5,
            )
            mic_idx = 0
            for line in (proc.stdout or "").splitlines():
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                name = parts[1]
                # PulseAudio sources include monitors (loopback); skip them.
                if name.endswith(".monitor"):
                    continue
                out.append({
                    "kind": "microphone", "name": name, "index": mic_idx,
                    "platform": "linux", "driver": "pulse",
                })
                mic_idx += 1
        except (subprocess.TimeoutExpired, OSError):
            pass
    return out


def list_sources(kind: SourceKind | None = None) -> List[Source]:
    """
    Enumerate available capture devices on the current OS.

    Parameters
    ----------
    kind : ``"camera"`` | ``"microphone"`` | None
        Filter to one kind. ``None`` (default) returns both.

    Returns
    -------
    list[Source]
        Possibly empty if ffmpeg is missing or the OS driver returns
        nothing parseable. Never raises.

    Examples
    --------
    >>> from capture_helper import list_sources
    >>> for s in list_sources("microphone"):
    ...     print(f"[{s['index']}] {s['name']} (driver={s['driver']})")
    """
    system = platform.system().lower()

    sources: List[Source]
    if system == "darwin":
        stderr = _run_ffmpeg_list_devices("avfoundation")
        sources = _parse_avfoundation_devices(stderr)
    elif system == "windows":
        stderr = _run_ffmpeg_list_devices("dshow")
        sources = _parse_dshow_devices(stderr)
    elif system == "linux":
        sources = _list_linux_devices()
    else:
        sources = []

    if kind is not None:
        sources = [s for s in sources if s["kind"] == kind]
    return sources
