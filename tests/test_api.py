"""
Smoke tests for the FastAPI HTTP surface.

Only exercises endpoints that don't touch real capture hardware
(``/health``, ``/sources``, and OpenAPI introspection to catch
endpoint-name drift). Live-capture endpoints would need a real
camera / mic and OS permission — out of scope for a smoke suite.

Usage Example
-------------
>>> #   pytest tests/test_api.py

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import pytest

# FastAPI is in the ``[api]`` optional extra — skip cleanly otherwise.
fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client():
    """Yield a TestClient bound to the capture-helper FastAPI app."""
    from capture_helper.api import app

    with TestClient(app) as c:
        yield c


def test_health_returns_ok(client):
    """``/health`` should return 200 + ``{"status": "ok"}``."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_openapi_lists_expected_endpoints(client):
    """The OpenAPI spec should list every expected route path."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    expected = {
        "/health",
        "/sources",
        "/pick",
        "/input-args",
        "/capture/camera",
        "/capture/mic",
        # scene configurator + live preview surfaces (v0.3.0)
        "/gui",
        "/preview/camera.jpg",
        "/preview/camera.mjpeg",
        "/preview/mic-level",
        "/scene",
        "/scene/save",
        "/scene/load",
    }
    assert expected.issubset(set(paths.keys()))


def test_docs_endpoint_is_served(client):
    """``/docs`` should serve the Swagger UI landing HTML."""
    r = client.get("/docs")
    assert r.status_code == 200
    assert "swagger" in r.text.lower() or "openapi" in r.text.lower()


def test_sources_endpoint_returns_list(client):
    """``/sources`` must return a JSON array — content depends on host OS."""
    r = client.get("/sources")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_pick_returns_404_when_no_match(client):
    """``/pick`` with an impossible name should surface as HTTP 404."""
    r = client.get(
        "/pick",
        params={"kind": "camera", "name": "definitely-not-a-real-device-xyz-42"},
    )
    # Either 404 (no matching device / no devices at all) — both are
    # legitimate responses on a headless CI runner.
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Scene configurator GUI + endpoints (v0.3.0)
# ---------------------------------------------------------------------------


def _page_name() -> str:
    """The GUI's own name, in whatever language it renders by default.

    Escaped the way the page escapes it: a French title can carry an
    apostrophe, which `render_gui` writes as `&#x27;` — correct HTML that a
    browser renders as an apostrophe, and not the literal the locale file
    holds.
    """
    import html

    from capture_helper import gui

    return html.escape(gui._locales().text("gui", "hero_title"), quote=True).lower()


def test_gui_returns_200_html(client):
    """``GET /gui`` should return 200 with a self-contained configurator page."""
    r = client.get("/gui")
    assert r.status_code == 200
    # It must be an HTML document (correct content type + a doctype).
    assert r.headers["content-type"].startswith("text/html")
    body = r.text.lower()
    assert "<!doctype html>" in body
    # Sanity-check it is the scene configurator and wires the real endpoints.
    # Ask the locale file what the page is called rather than hard-coding one
    # language's wording: the page renders in French by default, so asserting
    # the English copy would be testing the default locale, not the page.
    assert _page_name() in body
    assert "/sources" in r.text and "/preview/camera.mjpeg" in r.text
    assert "/scene/save" in r.text and "/scene/load" in r.text


def test_root_redirects_to_gui(client):
    """``GET /`` should redirect (or resolve) to the GUI page."""
    # follow_redirects defaults True in the TestClient; assert we land on HTML.
    r = client.get("/")
    assert r.status_code == 200
    assert _page_name() in r.text.lower()


def test_scene_auto_returns_valid_scene(client):
    """``GET /scene`` returns a well-formed scene (empty of sources on headless CI)."""
    r = client.get("/scene")
    assert r.status_code == 200
    scene = r.json()
    # Structural invariants that hold regardless of host devices.
    assert scene["width"] > 0 and scene["height"] > 0
    assert isinstance(scene["sources"], list)


def test_scene_save_load_round_trip(client):
    """A scene POSTed to ``/scene/save`` round-trips through ``/scene/load``."""
    scene = {
        "format_version": 1,
        "name": "roundtrip",
        "width": 640,
        "height": 360,
        "sources": [
            {
                "id": "abc123",
                "kind": "camera",
                "label": "cam",
                "name_substring": "cam",
                "index": 0,
                "x": 0,
                "y": 0,
                "w": 640,
                "h": 360,
                "z": 0,
                "params": {"fps": 10},
            }
        ],
    }
    # Save returns the validated artifact as a downloadable JSON file.
    r = client.post("/scene/save", json=scene)
    assert r.status_code == 200
    saved = r.content
    # Feed the saved bytes back through load; it must validate + echo the scene.
    r2 = client.post(
        "/scene/load",
        files={"file": ("roundtrip.scene.json", saved, "application/json")},
    )
    assert r2.status_code == 200
    back = r2.json()
    assert back["name"] == "roundtrip"
    assert len(back["sources"]) == 1 and back["sources"][0]["label"] == "cam"


def test_scene_save_rejects_malformed(client):
    """A malformed scene body should be a clean 400, not a 500."""
    r = client.post("/scene/save", json={"not": "a scene"})
    assert r.status_code == 400


def test_scene_save_sanitizes_path_traversal_name(client, tmp_path, monkeypatch):
    """A ``name`` containing "../" must not let the client write outside the
    request's own temp dir (path traversal / arbitrary file write)."""
    import capture_helper.api as api_module

    # Point capture-helper's temp-dir factory at a directory we control so we
    # can assert nothing landed outside it, without touching the real /tmp.
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    monkeypatch.setattr(
        api_module, "_new_tmpdir", lambda: api_module.Path(sandbox) / "capture-helper-test"
    )
    (sandbox / "capture-helper-test").mkdir()

    # ``tmp`` (the request-scoped dir the endpoint writes into) is
    # ``sandbox/capture-helper-test``; "../outside/pwned" climbs one level
    # out of it and back down into a sibling "outside" dir — i.e. it
    # attempts to write to ``sandbox/outside/pwned.scene.json``, a location
    # the request never created and has no business touching.
    canary = sandbox / "outside" / "pwned.scene.json"
    scene = {
        "format_version": 1,
        "name": "../outside/pwned",
        "width": 640,
        "height": 360,
        "sources": [],
    }
    r = client.post("/scene/save", json=scene)
    assert r.status_code == 200
    # The traversal must have been neutralized: nothing was written at the
    # attempted escape path, and no new "outside" directory was created.
    assert not canary.exists()
    assert not (sandbox / "outside").exists()


def _tmp_snapshot() -> set[str]:
    """Snapshot the names of capture-helper's own request-scoped temp dirs."""
    import glob
    import tempfile

    return set(glob.glob(f"{tempfile.gettempdir()}/capture-helper-*"))


def test_scene_save_cleans_up_temp_dir_on_failure(client, monkeypatch):
    """A ``save_scene`` failure after the temp dir is created must not leak it.

    ``scene_save`` validates first (a malformed body never reaches this far,
    see the 400 test above), then creates its temp dir and calls
    ``save_scene`` — which used to run unguarded: any exception there left
    the temp dir behind forever, since the deferred background cleanup was
    only ever scheduled after a successful write. This library-level error
    isn't caught as an ``HTTPException`` anywhere, so it propagates through
    the test client rather than coming back as a response — the leak check
    is what matters here, not the (uncaught) exception itself.
    """
    import capture_helper.api as api_mod

    def _boom(*a, **k):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(api_mod, "save_scene", _boom)
    before = _tmp_snapshot()
    # Must be a scene that actually passes validate_scene, so the request
    # reaches save_scene() rather than short-circuiting on a 400.
    scene = {
        "format_version": 1,
        "name": "leaktest",
        "width": 640,
        "height": 360,
        "sources": [],
    }
    with pytest.raises(OSError, match="simulated disk failure"):
        client.post("/scene/save", json=scene)
    after = _tmp_snapshot()
    assert after == before, f"scene_save leaked a temp dir: {after - before}"


def test_capture_camera_cleans_up_temp_dir_on_failure(client, monkeypatch):
    """A camera-capture failure after the temp dir is created must not leak it.

    Same bug class as ``scene_save`` above: ``capture_camera`` creates its
    temp dir, then iterates ``iter_camera_frames`` unguarded — a failure
    partway through (unsupported mode, permission denied, device busy) used
    to leave the temp dir behind. Uncaught, so it propagates through the
    test client rather than coming back as a response.
    """
    import capture_helper.api as api_mod

    def _no_such_device(*a, **k):
        raise ValueError("No camera devices available")
        yield  # pragma: no cover — makes this a generator function

    monkeypatch.setattr(
        api_mod, "pick_source", lambda kind, name_substring=None, index=None: {"kind": "camera"}
    )
    monkeypatch.setattr(api_mod, "iter_camera_frames", _no_such_device)
    before = _tmp_snapshot()
    with pytest.raises(ValueError, match="No camera devices available"):
        client.get("/capture/camera")
    after = _tmp_snapshot()
    assert after == before, f"capture_camera leaked a temp dir: {after - before}"
