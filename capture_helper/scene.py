"""
capture_helper.scene
====================

Scene / configuration model for capture-helper's **live multi-source scene
configurator**. A *scene* is a reusable, serialisable description of a live
composition: a named canvas of a given pixel size, holding an ordered list of
named capture sources (cameras / microphones) each pinned to a rectangle of the
canvas with per-source capture parameters.

Why this module exists
----------------------
The browser GUI (served at ``GET /gui`` by :mod:`capture_helper.api`) lets a
user visually enumerate devices, drop several onto a canvas, live-preview them,
arrange them, and then **save the design as a JSON artifact**. That artifact is
exactly a :class:`Scene`. The CLI and the HTTP API can then *load* the same
JSON and drive the underlying iterators — the visual design becomes a headless,
scriptable capture recipe. This module is the shared, hardware-free core of
that round-trip: build → validate → save → load → resolve.

Design constraints
------------------
- **Purely additive.** Nothing here touches the existing iterator contracts
  (:func:`capture_helper.iter_camera_frames` / :func:`iter_mic_audio`). A
  :class:`SceneSource` merely *records selectors and parameters* that are later
  fed to those functions unchanged.
- **JSON only, no new dependency.** Scenes serialise to plain JSON via the
  standard library so the artifact is trivially diffable, version-controllable,
  and readable by any language.
- **Best-effort resolution.** :func:`resolve_scene_sources` matches each recorded
  source against the *current* machine's devices; a scene authored on one
  machine can be replayed on another as long as the device names / indices line
  up (or degrade gracefully when they do not).

Usage example
-------------
>>> import capture_helper as ch
>>> scene = ch.new_scene("podcast", width=1280, height=720)
>>> scene = ch.add_source(scene, kind="camera", name_substring="FaceTime",
...                       x=0, y=0, w=1280, h=720, label="host cam")
>>> scene = ch.add_source(scene, kind="microphone", name_substring="Built-in",
...                       x=0, y=0, w=0, h=0, label="host mic")
>>> ch.save_scene(scene, "podcast.scene.json")
>>> reloaded = ch.load_scene("podcast.scene.json")
>>> reloaded["name"]
'podcast'

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, TypedDict

import os_helper as osh

from .sources import Source, SourceKind, list_sources, pick_source

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# On-disk format version. Bumped only if the JSON shape changes in a way that
# needs migration — readers can branch on it. Kept separate from the package
# SemVer so a scene file is not tied to a specific capture-helper release.
SCENE_FORMAT_VERSION: int = 1

# Default canvas size — 720p is a sane, widely-supported streaming baseline and
# matches the GUI's default aspect ratio.
DEFAULT_CANVAS_WIDTH: int = 1280
DEFAULT_CANVAS_HEIGHT: int = 720

# Filename suffix convention for scene artifacts. Not enforced (any path works),
# but the GUI / CLI default to it so scenes are recognisable on disk.
SCENE_SUFFIX: str = ".scene.json"


# ---------------------------------------------------------------------------
# Typed structures
# ---------------------------------------------------------------------------


class SceneSource(TypedDict):
    """One source placed on a scene canvas.

    A :class:`SceneSource` is a *recipe*, not a live handle: it records how to
    re-select the device (``kind`` + optional ``name_substring`` / ``index``),
    where it sits on the canvas (``x``/``y``/``w``/``h``/``z``), and the capture
    parameters to pass to the iterators when the scene is run.

    Keys
    ----
    id : str
        Stable, GUI-generated identifier (uuid4 hex) so the front-end can
        address a placed source across drag / resize / delete without relying on
        list order.
    kind : ``"camera"`` | ``"microphone"``
        Which iterator this source drives.
    label : str
        Human-friendly name shown in the GUI (e.g. ``"host cam"``). Free text.
    name_substring : str | None
        Case-insensitive substring used to re-resolve the device via
        :func:`capture_helper.pick_source`. ``None`` = no name constraint.
    index : int | None
        Exact device index used to re-resolve the device. ``None`` = no index
        constraint. When both are ``None`` the first device of ``kind`` is used.
    x, y : int
        Top-left position of the source's tile on the canvas, in pixels.
    w, h : int
        Tile size in pixels. For microphones (no visual) these may be ``0``.
    z : int
        Stacking order — higher draws on top. Cameras only.
    params : dict
        Free-form capture parameters forwarded to the iterator. For cameras:
        ``fps``, ``output_width``, ``output_height``, ``pad_color``. For
        microphones: ``target_sample_rate``, ``frame_ms``, ``to_mono``. Unknown
        keys are ignored by the runner, so the GUI can round-trip extras safely.
    """

    id: str
    kind: SourceKind
    label: str
    name_substring: str | None
    index: int | None
    x: int
    y: int
    w: int
    h: int
    z: int
    params: dict[str, Any]


class Scene(TypedDict):
    """A named, serialisable multi-source composition.

    Keys
    ----
    format_version : int
        On-disk schema version (:data:`SCENE_FORMAT_VERSION`).
    name : str
        Human name for the scene (also the suggested filename stem).
    width, height : int
        Canvas size in pixels. Source tiles are positioned within this box.
    sources : list[SceneSource]
        Ordered list of placed sources (draw order for cameras is by ``z``,
        ties broken by list order).
    """

    format_version: int
    name: str
    width: int
    height: int
    sources: list[SceneSource]


class ResolvedSceneSource(TypedDict):
    """A :class:`SceneSource` paired with the live device it resolved to.

    Keys
    ----
    scene_source : SceneSource
        The original recipe from the scene.
    resolved : Source | None
        The live :class:`capture_helper.Source` matched on this machine, or
        ``None`` when no device satisfied the recipe's selectors.
    error : str | None
        Human-readable reason the recipe could not be resolved, or ``None`` on
        success.
    """

    scene_source: SceneSource
    resolved: Source | None
    error: str | None


# ---------------------------------------------------------------------------
# Construction helpers
# ---------------------------------------------------------------------------


def new_scene(
    name: str = "untitled",
    *,
    width: int = DEFAULT_CANVAS_WIDTH,
    height: int = DEFAULT_CANVAS_HEIGHT,
) -> Scene:
    """
    Create an empty scene with a named canvas.

    Parameters
    ----------
    name : str, default ``"untitled"``
        Human name for the scene; also the suggested filename stem.
    width, height : int
        Canvas size in pixels. Defaults to 1280x720.

    Returns
    -------
    Scene
        A scene with no sources yet.

    Raises
    ------
    ValueError
        If ``width`` or ``height`` is not a positive integer.

    Examples
    --------
    >>> s = new_scene("demo", width=640, height=360)
    >>> s["width"], s["height"], s["sources"]
    (640, 360, [])
    """
    # Fail loudly on a nonsensical canvas — a zero/negative box would make every
    # downstream layout computation degenerate.
    if width <= 0 or height <= 0:
        raise ValueError(f"canvas must be positive, got {width}x{height}")
    return {
        "format_version": SCENE_FORMAT_VERSION,
        "name": name,
        "width": int(width),
        "height": int(height),
        "sources": [],
    }


def add_source(
    scene: Scene,
    *,
    kind: SourceKind,
    name_substring: str | None = None,
    index: int | None = None,
    label: str | None = None,
    x: int = 0,
    y: int = 0,
    w: int = 0,
    h: int = 0,
    z: int = 0,
    params: dict[str, Any] | None = None,
    source_id: str | None = None,
) -> Scene:
    """
    Return a copy of ``scene`` with one additional placed source.

    The input scene is **not mutated** — a shallow copy with a new ``sources``
    list is returned, so callers holding the old scene keep it intact (matches
    the immutable-update convention used across the suite's config helpers).

    Parameters
    ----------
    scene : Scene
        The scene to extend.
    kind : ``"camera"`` | ``"microphone"``
        Source kind.
    name_substring : str, optional
        Case-insensitive device-name filter recorded for later resolution.
    index : int, optional
        Exact device-index filter recorded for later resolution.
    label : str, optional
        Display name. Defaults to a generated ``"<kind> N"`` label.
    x, y, w, h, z : int
        Canvas placement (see :class:`SceneSource`).
    params : dict, optional
        Capture parameters forwarded to the iterator at run time.
    source_id : str, optional
        Explicit id (uuid4 hex). Generated when omitted — the GUI usually
        supplies its own so the round-trip is stable.

    Returns
    -------
    Scene
        A new scene including the added source.

    Examples
    --------
    >>> s = new_scene("demo")
    >>> s2 = add_source(s, kind="camera", label="cam", w=1280, h=720)
    >>> len(s["sources"]), len(s2["sources"])
    (0, 1)
    """
    # Auto-label as "<kind> <n>" when the caller did not name the tile — keeps
    # the GUI list readable even for quick drops.
    if label is None:
        n_same = sum(1 for s in scene["sources"] if s["kind"] == kind) + 1
        label = f"{kind} {n_same}"

    # Build the recipe entry. ``params or {}`` avoids sharing a mutable default.
    entry: SceneSource = {
        "id": source_id or uuid.uuid4().hex,
        "kind": kind,
        "label": label,
        "name_substring": name_substring,
        "index": index,
        "x": int(x),
        "y": int(y),
        "w": int(w),
        "h": int(h),
        "z": int(z),
        "params": dict(params or {}),
    }

    # Immutable update: copy the scene and append to a fresh list.
    updated: Scene = dict(scene)  # type: ignore[assignment]
    updated["sources"] = [*scene["sources"], entry]
    return updated


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_scene(scene: Any) -> Scene:
    """
    Validate an in-memory object as a well-formed :class:`Scene`.

    Cheap structural checks only — device availability is NOT verified here
    (that is :func:`resolve_scene_sources`' job, and depends on the host). This
    guards the save/load boundary so a corrupt or hand-edited file surfaces a
    clear error instead of an obscure ``KeyError`` deep in the runner.

    Parameters
    ----------
    scene : Any
        Candidate object (typically freshly parsed JSON).

    Returns
    -------
    Scene
        The same object, once every invariant holds (returned for chaining).

    Raises
    ------
    ValueError
        If any required key is missing or has the wrong type / value.

    Examples
    --------
    >>> validate_scene(new_scene("ok"))["name"]
    'ok'
    """
    # Top-level shape.
    if not isinstance(scene, dict):
        raise ValueError(f"scene must be a dict, got {type(scene).__name__}")
    for key in ("name", "width", "height", "sources"):
        if key not in scene:
            raise ValueError(f"scene missing required key: {key!r}")
    # Canvas must be a positive integer box.
    if not isinstance(scene["width"], int) or scene["width"] <= 0:
        raise ValueError(f"scene width must be a positive int, got {scene['width']!r}")
    if not isinstance(scene["height"], int) or scene["height"] <= 0:
        raise ValueError(f"scene height must be a positive int, got {scene['height']!r}")
    if not isinstance(scene["sources"], list):
        raise ValueError("scene 'sources' must be a list")

    # Per-source shape. We check each placed source so a single bad tile cannot
    # slip through to the runner.
    seen_ids: set[str] = set()
    for i, s in enumerate(scene["sources"]):
        if not isinstance(s, dict):
            raise ValueError(f"sources[{i}] must be a dict")
        if s.get("kind") not in ("camera", "microphone"):
            raise ValueError(f"sources[{i}].kind must be 'camera' or 'microphone'")
        # ids must exist and be unique so the GUI can address tiles reliably.
        sid = s.get("id")
        if not isinstance(sid, str) or not sid:
            raise ValueError(f"sources[{i}].id must be a non-empty string")
        if sid in seen_ids:
            raise ValueError(f"duplicate source id: {sid!r}")
        seen_ids.add(sid)
        # params must be a dict when present so the runner can splat it safely.
        if "params" in s and not isinstance(s["params"], dict):
            raise ValueError(f"sources[{i}].params must be a dict")
    return scene  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_scene(scene: Scene, path: str | Path) -> str:
    """
    Serialise a scene to a JSON file on disk.

    Parameters
    ----------
    scene : Scene
        The scene to persist. Validated before writing.
    path : str or Path
        Destination path. Parent directories are created if missing.

    Returns
    -------
    str
        The absolute path the scene was written to.

    Raises
    ------
    ValueError
        If ``scene`` fails :func:`validate_scene`.

    Examples
    --------
    >>> import tempfile, os
    >>> p = os.path.join(tempfile.mkdtemp(), "demo.scene.json")
    >>> _ = save_scene(new_scene("demo"), p)
    >>> os.path.exists(p)
    True
    """
    # Validate first so we never leave a malformed artifact on disk.
    validate_scene(scene)
    # Stamp the current format version on write (in case the in-memory object
    # was hand-built without it).
    scene = dict(scene)  # type: ignore[assignment]
    scene["format_version"] = SCENE_FORMAT_VERSION

    out = Path(path)
    # Ensure the parent folder exists — use os_helper so behaviour matches the
    # rest of the suite (and so the log trail is consistent).
    if out.parent and not out.parent.exists():
        osh.make_directory(str(out.parent))

    # Pretty-print for human diffability; scenes are small and mostly hand-read.
    out.write_text(json.dumps(scene, indent=2, ensure_ascii=False), encoding="utf-8")
    osh.info("capture-helper: saved scene %r -> %s", scene["name"], str(out))
    return str(out.resolve())


def load_scene(path: str | Path) -> Scene:
    """
    Load and validate a scene from a JSON file.

    Parameters
    ----------
    path : str or Path
        Path to a scene JSON file.

    Returns
    -------
    Scene
        The parsed, validated scene.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    ValueError
        If the file is not valid JSON or not a well-formed scene.

    Examples
    --------
    >>> import tempfile, os
    >>> p = os.path.join(tempfile.mkdtemp(), "demo.scene.json")
    >>> _ = save_scene(new_scene("demo"), p)
    >>> load_scene(p)["name"]
    'demo'
    """
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(f"scene file not found: {src}")
    # Parse defensively — a truncated / hand-edited file should give a clear
    # ValueError, not a raw json.JSONDecodeError leaking to the caller.
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"scene file is not valid JSON: {src} ({exc})") from exc
    return validate_scene(data)


# ---------------------------------------------------------------------------
# Resolution — map a scene onto the current machine's devices
# ---------------------------------------------------------------------------


def resolve_scene_sources(scene: Scene) -> list[ResolvedSceneSource]:
    """
    Match every scene source against the current machine's live devices.

    A scene authored elsewhere (or before a device was plugged in) may not fully
    resolve here. Rather than raising on the first miss, this returns one
    :class:`ResolvedSceneSource` per recipe so the GUI / CLI can report exactly
    which tiles are live and which are dangling.

    Parameters
    ----------
    scene : Scene
        The scene to resolve.

    Returns
    -------
    list[ResolvedSceneSource]
        One entry per source in ``scene["sources"]``, in the same order.

    Examples
    --------
    >>> res = resolve_scene_sources(new_scene("empty"))
    >>> res
    []
    """
    validate_scene(scene)
    out: list[ResolvedSceneSource] = []
    for s in scene["sources"]:
        # ``pick_source`` raises ValueError when nothing matches — we catch it
        # so one dangling tile does not sink the whole scene.
        try:
            live = pick_source(
                s["kind"],
                name_substring=s.get("name_substring"),
                index=s.get("index"),
            )
            out.append({"scene_source": s, "resolved": live, "error": None})
        except ValueError as exc:
            out.append({"scene_source": s, "resolved": None, "error": str(exc)})
    return out


def scene_from_available_devices(name: str = "auto") -> Scene:
    """
    Build a starter scene from whatever devices this machine reports.

    Convenience used by the GUI's "auto-populate" button and by the docs: grabs
    the first camera (full-canvas) and the first microphone (if any) so the user
    has something live to arrange instead of a blank canvas.

    Parameters
    ----------
    name : str, default ``"auto"``
        Name for the generated scene.

    Returns
    -------
    Scene
        A scene seeded with up to one camera and one microphone. Empty of
        sources when the host reports no devices (e.g. headless CI).

    Examples
    --------
    >>> isinstance(scene_from_available_devices(), dict)
    True
    """
    scene = new_scene(name)
    # First camera fills the canvas — the most common single-cam layout.
    cams = list_sources("camera")
    if cams:
        c = cams[0]
        scene = add_source(
            scene,
            kind="camera",
            name_substring=c["name"],
            index=c["index"],
            label=c["name"],
            x=0,
            y=0,
            w=scene["width"],
            h=scene["height"],
            z=0,
            params={"output_width": scene["width"], "output_height": scene["height"], "fps": 30},
        )
    # First microphone rides along (no visual footprint; w/h stay 0).
    mics = list_sources("microphone")
    if mics:
        m = mics[0]
        scene = add_source(
            scene,
            kind="microphone",
            name_substring=m["name"],
            index=m["index"],
            label=m["name"],
            params={"target_sample_rate": 16000, "frame_ms": 20, "to_mono": True},
        )
    return scene
