"""Capture Helper: Model Context Protocol (MCP) surface.

A thin adapter that exposes the FastAPI app from :mod:`capture_helper.api` as
MCP tools, so any MCP-aware host (an agent runtime, an IDE integration, a
custom shell) can call the camera/microphone capture layer as first-class
tools: device enumeration and selection, one-shot camera/mic capture, live
preview (JPEG/MJPEG/mic level), and the scene configurator (save/load/
auto-populate). Uses `fastapi-mcp` (https://github.com/tadata-org/fastapi_mcp):
one wrapper publishes the whole existing HTTP surface, so the routes are
never duplicated.

**Caveat for MCP hosts:** several tools here (``capture_camera``,
``capture_mic``, ``preview_camera_jpg``, ``preview_camera_mjpeg``,
``preview_mic_level``) open a REAL local camera or microphone device on the
machine running this server. An agent calling them will trigger an actual
hardware capture, not a simulation — treat them with the same care as any
other tool that touches physical I/O.

Install the extra to pull in ``fastapi-mcp``::

    pip install "capture-helper[mcp]"

Then run the server (HTTP API + MCP endpoint at ``/mcp``)::

    capture-helper-mcp                 # console entry point
    python -m capture_helper.mcp       # equivalent

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

try:
    from fastapi_mcp import FastApiMCP
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        'The MCP surface needs the [mcp] extra: pip install "capture-helper[mcp]"'
    ) from exc

# Reuse the exact same FastAPI app: MCP is a thin wrapper on top, no new routes.
from capture_helper.api import app

# Publish the HTTP endpoints (sources / pick / input-args / capture / preview /
# scene) as MCP tools.
mcp = FastApiMCP(
    app,
    name="capture-helper",
    description=(
        "capture-helper MCP tools: enumerate and select local camera/microphone "
        "devices, capture short camera-frame or microphone clips, live preview "
        "(JPEG snapshot, MJPEG stream, mic level), and the reusable scene "
        "configurator (save / load / auto-populate). Several tools open a real "
        "local camera or microphone — see this module's docstring."
    ),
)
# Newer fastapi-mcp splits mount() into transport-specific mount_http(); fall back to
# the legacy mount() so a range of fastapi-mcp versions keeps working.
if hasattr(mcp, "mount_http"):
    mcp.mount_http()
else:  # pragma: no cover - legacy fastapi-mcp
    mcp.mount()


def main() -> None:
    """Console entry point (``capture-helper-mcp``): serve the API + MCP endpoint.

    Boots the FastAPI app (now serving both the plain HTTP routes and the
    ``/mcp`` MCP endpoint) with uvicorn in a single worker. Local-first: binds
    to loopback by default (override with ``CAPTURE_HELPER_HOST`` /
    ``CAPTURE_HELPER_PORT``).
    """
    import os

    import uvicorn

    host = os.environ.get("CAPTURE_HELPER_HOST", "127.0.0.1")
    port = int(os.environ.get("CAPTURE_HELPER_PORT", "8000"))
    print(f"Capture Helper API + MCP -> http://{host}:{port}  (MCP at /mcp)")
    uvicorn.run(app, host=host, port=port, workers=1)


if __name__ == "__main__":  # pragma: no cover
    main()
