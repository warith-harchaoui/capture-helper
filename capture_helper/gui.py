"""
Capture Helper — live multi-source scene configurator (single-page GUI).

This module holds nothing but the self-contained HTML document served by the
FastAPI app at ``GET /gui`` (see :mod:`capture_helper.api`). It is deliberately
build-step-free: one string of HTML + Tailwind (via CDN) + vanilla ES-module
JavaScript. No bundler, no framework, no npm — the whole page is a static asset
the API returns verbatim.

What the page does
------------------
- **Enumerate** every camera and microphone on the host (``GET /sources``).
- **Add** sources to a visual scene canvas (click a device to place it).
- **Live-preview** each camera tile as an MJPEG stream
  (``GET /preview/camera.mjpeg``) and each microphone as a live level meter
  polled from ``GET /preview/mic-level``.
- **Arrange** camera tiles: drag to move, edit x/y/w/z in the inspector.
- **Save** the design as a reusable JSON scene artifact (``POST /scene/save``)
  and **load** one back (``POST /scene/load`` via file upload, or the server's
  auto-populated scene from ``GET /scene``).

The page adds no server-side logic — it is purely a friendlier front door to the
same HTTP surface the CLI and MCP tools use. It mirrors the AI Helpers minimal
GUI convention (Tailwind CDN + vanilla JS, reduced-motion guard, focus rings).

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

# The entire GUI is this one HTML string, returned as-is by the ``/gui`` route.
# Tailwind is pulled from a CDN so there is no build step; the JavaScript is a
# single inline ES module talking to the existing capture-helper API.
GUI_HTML: str = r"""<!doctype html>
<html lang="en" class="h-full">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Capture Helper — Scene Configurator</title>
  <!-- Tailwind via CDN: keeps the page a single self-contained file, no build. -->
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    /* Respect users who ask for reduced motion (accessibility baseline). */
    @media (prefers-reduced-motion: reduce) { *, *::before, *::after { transition: none !important; animation: none !important; } }
    /* The canvas keeps a 16:9 box; tiles are absolutely positioned inside it. */
    #canvas { aspect-ratio: 16 / 9; }
  </style>
</head>
<body class="h-full bg-slate-100 text-slate-900 antialiased">
  <div class="mx-auto max-w-7xl px-4 py-6">
    <header class="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="text-2xl font-semibold tracking-tight">Capture Helper — Scene Configurator</h1>
        <p class="mt-1 text-sm text-slate-600">
          Live multi-source scene configurator. Enumerate your cameras &amp; microphones,
          drop them on the canvas, preview them live, arrange, then save the design as a
          reusable scene the CLI / API can replay. Local-first — nothing leaves your machine.
        </p>
      </div>
      <div class="flex items-center gap-2">
        <label for="scene-name" class="text-sm font-medium">Scene</label>
        <input id="scene-name" value="untitled" aria-label="Scene name"
               class="w-40 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm
                      focus:outline-none focus:ring-2 focus:ring-emerald-600" />
      </div>
    </header>

    <div class="grid grid-cols-1 gap-4 lg:grid-cols-[18rem_1fr_18rem]">
      <!-- ============ LEFT: device palette ============ -->
      <aside class="rounded-xl border border-slate-200 bg-white p-4">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-sm font-semibold">Devices</h2>
          <button id="refresh" title="Re-enumerate devices"
                  class="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium hover:bg-slate-200
                         focus:outline-none focus:ring-2 focus:ring-emerald-600">Refresh</button>
        </div>
        <p class="mb-2 text-xs text-slate-500">Click a device to add it to the scene.</p>

        <h3 class="mb-1 mt-3 text-xs font-semibold uppercase tracking-wide text-slate-400">Cameras</h3>
        <ul id="cams" class="space-y-1 text-sm"></ul>
        <h3 class="mb-1 mt-4 text-xs font-semibold uppercase tracking-wide text-slate-400">Microphones</h3>
        <ul id="mics" class="space-y-1 text-sm"></ul>

        <div id="palette-empty" class="mt-4 hidden rounded-lg bg-amber-50 p-3 text-xs text-amber-800">
          No devices reported. On a headless server this is expected. Locally, check OS
          camera / microphone permissions and that <code>ffmpeg</code> is installed.
        </div>
      </aside>

      <!-- ============ CENTER: canvas ============ -->
      <section>
        <div class="mb-2 flex flex-wrap items-center gap-2">
          <button id="autofill"
                  class="rounded-lg bg-slate-700 px-3 py-1.5 text-sm font-semibold text-white
                         hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-600">
            Auto-populate</button>
          <button id="clear"
                  class="rounded-lg bg-slate-100 px-3 py-1.5 text-sm font-semibold
                         hover:bg-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-600">
            Clear</button>
          <span class="ml-auto text-xs text-slate-500">Drag a camera tile to move it.</span>
        </div>
        <!-- The scene canvas. Camera tiles are absolutely positioned inside; the
             coordinate system is the scene's own pixel space, scaled to fit. -->
        <div id="canvas"
             class="relative w-full overflow-hidden rounded-xl border-2 border-slate-300 bg-slate-900">
          <div id="canvas-empty"
               class="absolute inset-0 flex items-center justify-center text-center text-sm text-slate-400">
            Empty scene — add a camera from the palette or hit Auto-populate.
          </div>
        </div>
        <!-- Microphone meters live under the canvas (no visual footprint on it). -->
        <div id="meters" class="mt-3 space-y-2"></div>
      </section>

      <!-- ============ RIGHT: inspector + save/load ============ -->
      <aside class="rounded-xl border border-slate-200 bg-white p-4">
        <h2 class="mb-3 text-sm font-semibold">Inspector</h2>
        <div id="inspector" class="text-sm text-slate-500">Select a source to edit it.</div>

        <hr class="my-4 border-slate-200" />
        <h2 class="mb-2 text-sm font-semibold">Canvas size</h2>
        <div class="grid grid-cols-2 gap-2">
          <label class="text-xs">width
            <input id="canvas-w" type="number" value="1280"
                   class="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1 text-sm" /></label>
          <label class="text-xs">height
            <input id="canvas-h" type="number" value="720"
                   class="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1 text-sm" /></label>
        </div>

        <hr class="my-4 border-slate-200" />
        <h2 class="mb-2 text-sm font-semibold">Scene artifact</h2>
        <div class="flex flex-col gap-2">
          <button id="save"
                  class="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white
                         hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-600">
            Save scene (JSON)</button>
          <label class="rounded-lg border border-slate-300 px-3 py-2 text-center text-sm font-medium
                        cursor-pointer hover:bg-slate-50 focus-within:ring-2 focus-within:ring-emerald-600">
            Load scene…
            <input id="load-file" type="file" accept=".json,application/json" class="hidden" />
          </label>
          <button id="show-json"
                  class="rounded-lg bg-slate-100 px-3 py-2 text-sm font-medium hover:bg-slate-200
                         focus:outline-none focus:ring-2 focus:ring-emerald-600">
            Show scene JSON</button>
        </div>
        <span id="status" class="mt-2 block text-xs text-slate-600" role="status" aria-live="polite"></span>
        <pre id="json" class="mt-2 hidden max-h-64 overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-emerald-200"></pre>
      </aside>
    </div>
  </div>

  <script type="module">
    // ------------------------------------------------------------------ helpers
    const $ = (id) => document.getElementById(id);
    const status = (m) => { $("status").textContent = m; };
    const uid = () => (crypto.randomUUID ? crypto.randomUUID().replace(/-/g, "") : String(Math.random()).slice(2));

    // The in-memory scene. Mirrors capture_helper.scene.Scene exactly so the
    // save/load round-trip through the API is loss-free.
    const scene = { format_version: 1, name: "untitled", width: 1280, height: 720, sources: [] };
    let selectedId = null;                 // currently-inspected source id
    const meterTimers = new Map();         // mic id -> interval handle

    // ------------------------------------------------------------ device palette
    // Fetch the host's devices and render the clickable palette.
    async function loadDevices() {
      status("Enumerating devices…");
      let list = [];
      try {
        const r = await fetch("/sources");
        list = await r.json();
      } catch (e) { status("Could not reach the API: " + e); return; }
      const cams = list.filter((s) => s.kind === "camera");
      const mics = list.filter((s) => s.kind === "microphone");
      renderPalette($("cams"), cams, "camera");
      renderPalette($("mics"), mics, "microphone");
      $("palette-empty").classList.toggle("hidden", list.length > 0);
      status(list.length ? `Found ${cams.length} camera(s), ${mics.length} mic(s).` : "No devices found.");
    }

    // Render one device list; clicking an entry adds it to the scene.
    function renderPalette(ul, devices, kind) {
      ul.innerHTML = "";
      for (const d of devices) {
        const li = document.createElement("li");
        const btn = document.createElement("button");
        btn.className = "w-full truncate rounded-md border border-slate-200 px-2 py-1 text-left " +
                        "hover:bg-emerald-50 focus:outline-none focus:ring-2 focus:ring-emerald-600";
        btn.textContent = `[${d.index}] ${d.name}`;
        btn.title = `${d.driver} · ${d.platform}`;
        btn.addEventListener("click", () => addSource(kind, d));
        li.appendChild(btn); ul.appendChild(li);
      }
    }

    // -------------------------------------------------------------- scene edits
    // Add a device to the scene (default full-canvas for a first camera).
    function addSource(kind, d) {
      const isCam = kind === "camera";
      const src = {
        id: uid(), kind, label: d.name, name_substring: d.name, index: d.index,
        x: 0, y: 0,
        w: isCam ? scene.width : 0, h: isCam ? scene.height : 0, z: scene.sources.length,
        params: isCam
          ? { output_width: scene.width, output_height: scene.height, fps: 10 }
          : { target_sample_rate: 16000, frame_ms: 20, to_mono: true },
      };
      scene.sources.push(src);
      render();
      select(src.id);
    }

    // Remove a source (and stop its meter if it is a mic).
    function removeSource(id) {
      const s = scene.sources.find((x) => x.id === id);
      if (s && meterTimers.has(id)) { clearInterval(meterTimers.get(id)); meterTimers.delete(id); }
      scene.sources = scene.sources.filter((x) => x.id !== id);
      if (selectedId === id) selectedId = null;
      render();
    }

    // ------------------------------------------------------------ rendering
    // Redraw the canvas tiles, the mic meters, and the inspector from `scene`.
    function render() {
      scene.name = $("scene-name").value || "untitled";
      scene.width = parseInt($("canvas-w").value, 10) || 1280;
      scene.height = parseInt($("canvas-h").value, 10) || 720;

      const canvas = $("canvas");
      // Wipe every tile but keep the empty-state hint element.
      [...canvas.querySelectorAll("[data-tile]")].forEach((n) => n.remove());
      const cams = scene.sources.filter((s) => s.kind === "camera");
      $("canvas-empty").classList.toggle("hidden", cams.length > 0);

      const rect = canvas.getBoundingClientRect();
      const sx = rect.width / scene.width, sy = rect.height / scene.height;

      for (const s of cams.sort((a, b) => a.z - b.z)) {
        const tile = document.createElement("div");
        tile.dataset.tile = s.id;
        tile.className = "absolute overflow-hidden rounded-md ring-2 " +
          (s.id === selectedId ? "ring-emerald-400" : "ring-white/40");
        tile.style.left = (s.x * sx) + "px";
        tile.style.top = (s.y * sy) + "px";
        tile.style.width = (s.w * sx) + "px";
        tile.style.height = (s.h * sy) + "px";
        tile.style.zIndex = String(s.z + 1);

        // Live MJPEG preview as the tile background. The endpoint resolves the
        // device by name/index; a query cache-buster keeps streams distinct.
        const img = document.createElement("img");
        const q = new URLSearchParams();
        if (s.name_substring) q.set("name", s.name_substring);
        if (s.index != null) q.set("index", String(s.index));
        q.set("t", s.id);
        img.src = "/preview/camera.mjpeg?" + q.toString();
        img.alt = "Live preview of " + s.label;
        img.className = "h-full w-full object-cover";
        img.addEventListener("error", () => {
          // No live device (headless / permission) → show a placeholder label.
          img.replaceWith(Object.assign(document.createElement("div"), {
            className: "flex h-full w-full items-center justify-center bg-slate-800 text-xs text-slate-400",
            textContent: s.label + " (no live preview)",
          }));
        });
        tile.appendChild(img);

        // A caption strip so the tile is identifiable even at small sizes.
        const cap = document.createElement("div");
        cap.className = "absolute inset-x-0 bottom-0 truncate bg-black/50 px-1 py-0.5 text-[10px] text-white";
        cap.textContent = s.label;
        tile.appendChild(cap);

        tile.addEventListener("mousedown", (e) => startDrag(e, s, sx, sy));
        tile.addEventListener("click", () => select(s.id));
        canvas.appendChild(tile);
      }

      renderMeters();
      renderInspector();
    }

    // Draw one live level meter per microphone source and poll it.
    function renderMeters() {
      const box = $("meters");
      const mics = scene.sources.filter((s) => s.kind === "microphone");
      box.innerHTML = "";
      // Stop timers for mics that no longer exist.
      for (const [id, h] of meterTimers) if (!mics.find((m) => m.id === id)) { clearInterval(h); meterTimers.delete(id); }

      for (const m of mics) {
        const row = document.createElement("div");
        row.className = "rounded-lg border border-slate-200 bg-white p-2";
        row.innerHTML =
          `<div class="mb-1 flex items-center justify-between text-xs">
             <span class="truncate font-medium">🎙 ${m.label}</span>
             <span data-db="${m.id}" class="tabular-nums text-slate-500">-∞ dBFS</span>
           </div>
           <div class="h-2 w-full overflow-hidden rounded bg-slate-200">
             <div data-bar="${m.id}" class="h-full w-0 bg-emerald-500"></div>
           </div>`;
        row.addEventListener("click", () => select(m.id));
        box.appendChild(row);
        if (!meterTimers.has(m.id)) startMeter(m);
      }
    }

    // Poll the mic-level endpoint on a light interval and animate the bar.
    function startMeter(m) {
      const tick = async () => {
        const q = new URLSearchParams();
        if (m.name_substring) q.set("name", m.name_substring);
        if (m.index != null) q.set("index", String(m.index));
        try {
          const r = await fetch("/preview/mic-level?" + q.toString());
          if (!r.ok) return;
          const j = await r.json();
          const bar = document.querySelector(`[data-bar="${m.id}"]`);
          const lbl = document.querySelector(`[data-db="${m.id}"]`);
          if (!bar) return;
          // Map -60..0 dBFS to 0..100% width.
          const pct = Math.max(0, Math.min(100, ((j.rms_dbfs + 60) / 60) * 100));
          bar.style.width = pct + "%";
          bar.className = "h-full " + (j.rms_dbfs > -6 ? "bg-red-500" : j.rms_dbfs > -20 ? "bg-amber-400" : "bg-emerald-500");
          if (lbl) lbl.textContent = (j.rms_dbfs <= -119 ? "-∞" : j.rms_dbfs.toFixed(1)) + " dBFS";
        } catch (_) { /* transient — ignore, next tick retries */ }
      };
      meterTimers.set(m.id, setInterval(tick, 500));
      tick();
    }

    // ------------------------------------------------------------- drag to move
    // Move a camera tile within the canvas, in scene-pixel coordinates.
    function startDrag(e, s, sx, sy) {
      e.preventDefault();
      const startX = e.clientX, startY = e.clientY, ox = s.x, oy = s.y;
      const onMove = (ev) => {
        s.x = Math.round(ox + (ev.clientX - startX) / sx);
        s.y = Math.round(oy + (ev.clientY - startY) / sy);
        // Clamp inside the canvas so tiles never fully escape.
        s.x = Math.max(0, Math.min(scene.width - 1, s.x));
        s.y = Math.max(0, Math.min(scene.height - 1, s.y));
        render();
      };
      const onUp = () => { document.removeEventListener("mousemove", onMove); document.removeEventListener("mouseup", onUp); };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    }

    // ------------------------------------------------------------- inspector
    function select(id) { selectedId = id; render(); }

    // Render editable fields for the selected source.
    function renderInspector() {
      const box = $("inspector");
      const s = scene.sources.find((x) => x.id === selectedId);
      if (!s) { box.innerHTML = '<span class="text-slate-500">Select a source to edit it.</span>'; return; }
      const numField = (key, label, val) =>
        `<label class="block text-xs">${label}
           <input data-f="${key}" type="number" value="${val}"
                  class="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-sm" /></label>`;
      const isCam = s.kind === "camera";
      box.innerHTML =
        `<div class="mb-2 flex items-center justify-between">
           <span class="rounded bg-slate-100 px-2 py-0.5 text-xs font-semibold">${s.kind}</span>
           <button id="del" class="text-xs font-medium text-red-600 hover:underline">Remove</button>
         </div>
         <label class="block text-xs">label
           <input data-f="label" value="${s.label}" class="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-sm" /></label>
         <div class="mt-2 grid grid-cols-2 gap-2">
           ${isCam ? numField("x", "x", s.x) + numField("y", "y", s.y) + numField("w", "w", s.w) + numField("z", "z (order)", s.z) : ""}
         </div>`;
      // Wire each editable field back into the scene object.
      box.querySelectorAll("[data-f]").forEach((inp) => {
        inp.addEventListener("input", () => {
          const k = inp.dataset.f;
          s[k] = (k === "label") ? inp.value : (parseInt(inp.value, 10) || 0);
          render();
        });
      });
      const del = $("del"); if (del) del.addEventListener("click", () => removeSource(s.id));
    }

    // ------------------------------------------------------------ save / load
    // Persist the scene via the API and offer the returned JSON for download.
    $("save").addEventListener("click", async () => {
      render();
      status("Saving…");
      try {
        const r = await fetch("/scene/save", {
          method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(scene),
        });
        if (!r.ok) { status("Save failed: " + (await r.text()).slice(0, 200)); return; }
        const blob = await r.blob();
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = (scene.name || "scene") + ".scene.json";
        a.click();
        status("Saved & downloaded.");
      } catch (e) { status("Save failed: " + e); }
    });

    // Load a scene file: validate it server-side, then adopt it locally.
    $("load-file").addEventListener("change", async (e) => {
      const f = e.target.files[0]; if (!f) return;
      status("Loading…");
      try {
        const fd = new FormData(); fd.append("file", f);
        const r = await fetch("/scene/load", { method: "POST", body: fd });
        if (!r.ok) { status("Load failed: " + (await r.text()).slice(0, 200)); return; }
        adopt(await r.json());
        status("Scene loaded.");
      } catch (err) { status("Load failed: " + err); }
    });

    // Replace the working scene with a validated one from the server.
    function adopt(s) {
      Object.assign(scene, s);
      $("scene-name").value = scene.name;
      $("canvas-w").value = scene.width;
      $("canvas-h").value = scene.height;
      selectedId = null;
      for (const h of meterTimers.values()) clearInterval(h);
      meterTimers.clear();
      render();
    }

    $("show-json").addEventListener("click", () => {
      render();
      const pre = $("json");
      pre.textContent = JSON.stringify(scene, null, 2);
      pre.classList.toggle("hidden");
    });

    // ------------------------------------------------------------ toolbar wiring
    $("refresh").addEventListener("click", loadDevices);
    $("clear").addEventListener("click", () => { scene.sources = []; selectedId = null; render(); });
    $("autofill").addEventListener("click", async () => {
      status("Auto-populating from the server…");
      try {
        const r = await fetch("/scene");   // server builds a scene from live devices
        adopt(await r.json());
        status("Auto-populated.");
      } catch (e) { status("Auto-populate failed: " + e); }
    });
    for (const id of ["scene-name", "canvas-w", "canvas-h"]) $(id).addEventListener("input", render);
    // Re-scale tiles when the window (hence the canvas) resizes.
    window.addEventListener("resize", render);

    // ------------------------------------------------------------ boot
    loadDevices();
    render();
  </script>
</body>
</html>
"""
