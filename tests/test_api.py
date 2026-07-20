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


def test_gui_returns_200_html(client):
    """``GET /gui`` should return 200 with a self-contained configurator page."""
    r = client.get("/gui")
    assert r.status_code == 200
    # It must be an HTML document (correct content type + a doctype).
    assert r.headers["content-type"].startswith("text/html")
    body = r.text.lower()
    assert "<!doctype html>" in body
    # Sanity-check it is the scene configurator and wires the real endpoints.
    assert "scene configurator" in body
    assert "/sources" in r.text and "/preview/camera.mjpeg" in r.text
    assert "/scene/save" in r.text and "/scene/load" in r.text


def test_root_redirects_to_gui(client):
    """``GET /`` should redirect (or resolve) to the GUI page."""
    # follow_redirects defaults True in the TestClient; assert we land on HTML.
    r = client.get("/")
    assert r.status_code == 200
    assert "scene configurator" in r.text.lower()


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
