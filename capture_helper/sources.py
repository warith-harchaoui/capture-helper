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

Usage Example
-------------
>>> from capture_helper.sources import list_sources, pick_source, ffmpeg_input_args
>>> for s in list_sources():
...     print(s["kind"], s["index"], s["name"], s["driver"])
>>> cam = pick_source("camera", name_substring="FaceTime")
>>> ffmpeg_input_args(cam)          # doctest: +SKIP
['-f', 'avfoundation', '-i', '0:none']

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
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


# ---------------------------------------------------------------------------
# pick_source — convenience selector over the catalog returned by list_sources
# ---------------------------------------------------------------------------


def pick_source(
    kind: SourceKind,
    *,
    name_substring: str | None = None,
    index: int | None = None,
) -> Source:
    """
    Pick a single capture device matching the given constraints.

    Runs :func:`list_sources` for ``kind`` and applies each non-None
    filter as a hard predicate. Returns the **first** remaining
    candidate (OS-listing order — usually "built-in first, peripherals
    after"). Raises ``ValueError`` if nothing matches.

    Parameters
    ----------
    kind : ``"camera"`` | ``"microphone"``
        Which kind of device to pick.
    name_substring : str, optional
        Case-insensitive substring filter against ``Source["name"]``.
        Useful to disambiguate when several devices of the same kind
        are present (``"BlackHole"``, ``"USB"``, ``"FaceTime"``, …).
    index : int, optional
        Exact match against ``Source["index"]``. When the OS reports
        stable indices (avfoundation, dshow), this picks a specific
        device unambiguously.

    Returns
    -------
    Source
        The chosen device.

    Raises
    ------
    ValueError
        If no device matches (either the catalog is empty, or every
        candidate is filtered out by the constraints).

    Examples
    --------
    >>> from capture_helper import pick_source
    >>> cam = pick_source("camera")                  # first available camera
    >>> mic = pick_source("microphone", name_substring="BlackHole")
    >>> usb_cam = pick_source("camera", index=1)
    """
    # ``list_sources`` already applies the OS routing and is best-effort
    # (returns ``[]`` rather than raising) — we re-raise here ourselves
    # so callers don't silently get a "None source" downstream.
    catalog = list_sources(kind)
    if not catalog:
        raise ValueError(
            f"No {kind} devices available "
            f"(is ffmpeg installed and on PATH? "
            f"have you granted the OS permission to enumerate {kind}s?)"
        )

    def _matches(s: Source) -> bool:
        # Case-insensitive substring lets the user type a fragment of
        # the actual device name without worrying about exact casing.
        if name_substring is not None and name_substring.lower() not in s["name"].lower():
            return False
        if index is not None and s["index"] != index:
            return False
        return True

    matching = [s for s in catalog if _matches(s)]
    if not matching:
        raise ValueError(
            f"No {kind} matches constraints "
            f"(name_substring={name_substring!r}, index={index!r}). "
            f"Catalog had {len(catalog)} candidate(s); "
            f"call list_sources({kind!r}) to inspect."
        )
    return matching[0]


# ---------------------------------------------------------------------------
# Per-OS ffmpeg input string builder — used by camera / mic iterators
# ---------------------------------------------------------------------------


def ffmpeg_input_args(source: Source) -> list[str]:
    """
    Build the ffmpeg ``-f <driver> -i <spec>`` argument pair for ``source``.

    Encapsulates the per-OS quirks so :mod:`capture_helper.camera` and
    :mod:`capture_helper.mic` don't have to know about them:

    - ``avfoundation`` (macOS) addresses devices as ``"<video_idx>:<audio_idx>"``
      where ``"none"`` opts out of the other track.
    - ``v4l2`` (Linux) uses the device path (``/dev/videoN``) reported
      by :func:`list_sources`.
    - ``pulse`` (Linux) and ``alsa`` (Linux) take the source/device name.
    - ``dshow`` (Windows) prefixes the device name with ``video=`` or
      ``audio=``.

    Parameters
    ----------
    source : Source
        A device dict returned by :func:`list_sources` /
        :func:`pick_source`.

    Returns
    -------
    list[str]
        Two elements: ``["-f", "<driver>"]`` followed by ``["-i", "<spec>"]``
        — ready to splice into an ffmpeg command line.

    Raises
    ------
    ValueError
        If the source's driver is unknown to this helper.
    """
    drv = source["driver"]
    if drv == "avfoundation":
        # AVFoundation: combined video/audio addressing. ``none`` opts
        # out of the channel we're not capturing.
        spec = f"{source['index']}:none" if source["kind"] == "camera" else f"none:{source['index']}"
        return ["-f", "avfoundation", "-i", spec]
    if drv == "v4l2":
        # v4l2 takes the device path directly (``/dev/videoN`` per
        # :func:`_list_linux_devices`).
        return ["-f", "v4l2", "-i", source["name"]]
    if drv == "dshow":
        # DirectShow names are prefixed by the track kind.
        kind_label = "video" if source["kind"] == "camera" else "audio"
        return ["-f", "dshow", "-i", f"{kind_label}={source['name']}"]
    if drv == "pulse":
        # PulseAudio source name as reported by ``pactl list short sources``.
        return ["-f", "pulse", "-i", source["name"]]
    if drv == "alsa":
        # ALSA hardware identifier (e.g. ``hw:1,0``).
        return ["-f", "alsa", "-i", source["name"]]
    raise ValueError(f"Unsupported source driver: {drv!r}")
