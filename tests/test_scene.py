"""
Unit tests for :mod:`capture_helper.scene`.

Hardware-free: exercises the scene model, validation, and the JSON save/load
round-trip. Device resolution is tested only for its graceful-degradation path
(no real camera / mic required).

Usage Example
-------------
>>> #   pytest tests/test_scene.py

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import json

import pytest

import capture_helper as ch
from capture_helper.scene import SCENE_FORMAT_VERSION


def test_new_scene_defaults():
    """A fresh scene has the default canvas and no sources."""
    s = ch.new_scene("demo")
    assert s["name"] == "demo"
    assert s["width"] > 0 and s["height"] > 0
    assert s["sources"] == []
    assert s["format_version"] == SCENE_FORMAT_VERSION


def test_new_scene_rejects_bad_canvas():
    """A non-positive canvas must raise."""
    with pytest.raises(ValueError):
        ch.new_scene("bad", width=0, height=100)


def test_add_source_is_immutable():
    """``add_source`` returns a new scene and never mutates the input."""
    s0 = ch.new_scene("demo")
    s1 = ch.add_source(s0, kind="camera", label="cam", w=1280, h=720)
    # Original untouched; new scene has the added tile.
    assert len(s0["sources"]) == 0
    assert len(s1["sources"]) == 1
    assert s1["sources"][0]["kind"] == "camera"
    # ids are generated and unique.
    assert s1["sources"][0]["id"]


def test_add_source_auto_labels():
    """Auto-labels increment per kind when no label is supplied."""
    s = ch.new_scene("demo")
    s = ch.add_source(s, kind="camera")
    s = ch.add_source(s, kind="camera")
    labels = [src["label"] for src in s["sources"]]
    assert labels == ["camera 1", "camera 2"]


def test_validate_scene_catches_errors():
    """Validation rejects the common malformed shapes."""
    # Not a dict.
    with pytest.raises(ValueError):
        ch.validate_scene([])
    # Missing key.
    with pytest.raises(ValueError):
        ch.validate_scene({"name": "x", "width": 10, "height": 10})
    # Bad source kind.
    bad = ch.new_scene("x")
    bad["sources"] = [{"id": "a", "kind": "screen", "params": {}}]
    with pytest.raises(ValueError):
        ch.validate_scene(bad)
    # Duplicate ids.
    dup = ch.new_scene("x")
    dup["sources"] = [
        {"id": "a", "kind": "camera", "params": {}},
        {"id": "a", "kind": "camera", "params": {}},
    ]
    with pytest.raises(ValueError):
        ch.validate_scene(dup)


def test_save_load_round_trip(tmp_path):
    """A scene survives a JSON save/load with identical content."""
    s = ch.new_scene("podcast", width=1280, height=720)
    s = ch.add_source(
        s, kind="camera", name_substring="Face", index=0, w=1280, h=720, params={"fps": 30}
    )
    s = ch.add_source(s, kind="microphone", name_substring="Built-in")
    path = tmp_path / "podcast.scene.json"
    ch.save_scene(s, path)
    assert path.exists()

    reloaded = ch.load_scene(path)
    assert reloaded["name"] == "podcast"
    assert len(reloaded["sources"]) == 2
    # The camera params round-trip verbatim.
    cam = next(x for x in reloaded["sources"] if x["kind"] == "camera")
    assert cam["params"]["fps"] == 30


def test_load_scene_missing_file(tmp_path):
    """Loading a non-existent path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        ch.load_scene(tmp_path / "nope.scene.json")


def test_load_scene_bad_json(tmp_path):
    """A non-JSON file raises a clear ValueError, not a JSONDecodeError."""
    p = tmp_path / "broken.scene.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        ch.load_scene(p)


def test_save_stamps_format_version(tmp_path):
    """Saving always stamps the current format version on the artifact."""
    s = ch.new_scene("x")
    # Strip the version to prove save re-stamps it.
    s.pop("format_version", None)  # type: ignore[misc]
    path = tmp_path / "x.scene.json"
    ch.save_scene(s, path)  # type: ignore[arg-type]
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["format_version"] == SCENE_FORMAT_VERSION


def test_resolve_empty_scene():
    """Resolving an empty scene yields an empty list (never raises)."""
    assert ch.resolve_scene_sources(ch.new_scene("empty")) == []


def test_resolve_dangling_source_degrades_gracefully():
    """A source that cannot resolve here is reported, not raised."""
    s = ch.new_scene("x")
    # A name that cannot possibly match a real device on any host.
    s = ch.add_source(s, kind="camera", name_substring="definitely-not-a-device-xyz-42")
    resolved = ch.resolve_scene_sources(s)
    assert len(resolved) == 1
    # Either it resolved (unlikely) or it carries an error string.
    r = resolved[0]
    assert r["resolved"] is None or isinstance(r["resolved"], dict)
    if r["resolved"] is None:
        assert isinstance(r["error"], str)


def test_scene_from_available_devices_is_valid():
    """The auto-populated scene is always structurally valid."""
    s = ch.scene_from_available_devices("auto")
    # Validation must pass whether or not the host has devices.
    ch.validate_scene(s)
    assert isinstance(s["sources"], list)
