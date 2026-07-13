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
