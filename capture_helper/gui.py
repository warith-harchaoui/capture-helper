"""
Capture Helper — live multi-source scene configurator (single-page GUI).

This module holds nothing but the self-contained HTML document served by the
FastAPI app at ``GET /gui`` (see :mod:`capture_helper.api`). It is deliberately
build-step-free: one string of HTML + Tailwind (via CDN) + vanilla ES-module
JavaScript. No bundler, no framework, no npm — the whole page is a static asset
the API returns verbatim.

Where the words live
--------------------
Not here. Every human-readable string comes from ``locales/i18n.yaml``
through :class:`os_helper.Locales`, the loader shared across the suite
(``CODING.md`` 21.3). The markup below is tokenised — ``{{TOKEN}}`` in HTML,
and a ``T`` object injected for the script — so one template serves every
language and a translator never touches Python.

:func:`render_gui` resolves a language and returns the finished page.

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

import functools
import html
import json
from pathlib import Path

import os_helper as osh

# Inside the package, not beside it: a file one level up is not package data
# and does not travel in the wheel. best-engine shipped exactly that bug —
# `pip install` gave a package whose every GUI string raised FileNotFoundError.
_LOCALES_PATH = Path(__file__).resolve().parent / "locales" / "i18n.yaml"

#: The section of the locale file this module reads.
_GUI_SECTION = "gui"


@functools.lru_cache(maxsize=1)
def _locales() -> osh.Locales:
    """Parse ``locales/i18n.yaml`` once, through the suite's shared loader."""
    return osh.Locales.from_path(_LOCALES_PATH)


def supported_languages() -> tuple[str, ...]:
    """Language codes the GUI can render, as declared by the locale file."""
    return tuple(_locales().supported_locales)


def default_language() -> str:
    """The language an unknown or absent ``?lang=`` falls back to."""
    return _locales().default_locale


# Two vocabularies meet here: the template's tokens and the locale file's
# semantic keys. These maps bridge them. `_HTML_TOKEN_TO_KEY` fills {{TOKEN}}
# placeholders; `_JS_NAME_TO_KEY` builds the `const T = {...}` the script reads.
_HTML_TOKEN_TO_KEY: dict[str, str] = {
    "PAGE_TITLE": "page_title",
    "HERO_TITLE": "hero_title",
    "HERO_P": "hero_subtitle",
    "SCENE_LABEL": "scene_label",
    "SCENE_NAME_ARIA": "scene_name_aria",
    "SCENE_NAME_DEFAULT": "scene_name_default",
    "DEVICES_H2": "devices_heading",
    "REFRESH_BUTTON": "refresh_button",
    "REFRESH_TITLE": "refresh_title",
    "PALETTE_HINT": "palette_hint",
    "CAMERAS_H3": "cameras_heading",
    "MICROPHONES_H3": "microphones_heading",
    "PALETTE_EMPTY_LEAD": "palette_empty_lead",
    "PALETTE_EMPTY_TAIL": "palette_empty_tail",
    "AUTOFILL_BUTTON": "autofill_button",
    "CLEAR_BUTTON": "clear_button",
    "DRAG_HINT": "drag_hint",
    "CANVAS_EMPTY": "canvas_empty",
    "INSPECTOR_H2": "inspector_heading",
    "INSPECTOR_EMPTY": "inspector_empty",
    "CANVAS_SIZE_H2": "canvas_size_heading",
    "WIDTH_LABEL": "width_label",
    "HEIGHT_LABEL": "height_label",
    "SCENE_ARTIFACT_H2": "scene_artifact_heading",
    "SAVE_BUTTON": "save_button",
    "LOAD_LABEL": "load_label",
    "SHOW_JSON_BUTTON": "show_json_button",
    "LANG_HREF": "lang_toggle_href",
    "LANG_FLAG": "lang_toggle_flag",
    "LANG_ARIA": "lang_toggle_aria",
}

_JS_NAME_TO_KEY: dict[str, str] = {
    "sceneNameDefault": "scene_name_default",
    "inspectorEmpty": "inspector_empty",
    "enumerating": "js_enumerating",
    "apiUnreachable": "js_api_unreachable",
    "found": "js_found",
    "noDevices": "js_no_devices",
    "previewAlt": "js_preview_alt",
    "noLivePreview": "js_no_live_preview",
    "removeButton": "js_remove_button",
    "labelField": "js_label_field",
    "zField": "js_z_field",
    "saving": "js_saving",
    "saveFailed": "js_save_failed",
    "saved": "js_saved",
    "loading": "js_loading",
    "loadFailed": "js_load_failed",
    "loaded": "js_loaded",
    "autofilling": "js_autofilling",
    "autofilled": "js_autofilled",
    "autofillFailed": "js_autofill_failed",
}


# One template, every language. Human-facing text is tokenised as {{TOKEN}}
# (HTML) or read from the injected `T` object (JavaScript); `render_gui` fills
# both. Tailwind is pulled from a CDN so there is no build step; the JavaScript
# is a single inline ES module talking to the existing capture-helper API.
_GUI_TEMPLATE: str = r"""<!doctype html>
<html lang="{{LANG}}" class="h-full">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{{PAGE_TITLE}}</title>
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
        <h1 class="text-2xl font-semibold tracking-tight">{{HERO_TITLE}}</h1>
        <p class="mt-1 text-sm text-slate-600">
          {{HERO_P}}
        </p>
      </div>
      <div class="flex items-center gap-2">
        <!-- Language toggle: a flag that links to the other locale of this page. -->
        <a href="{{LANG_HREF}}" aria-label="{{LANG_ARIA}}"
           class="text-xl hover:opacity-70">{{LANG_FLAG}}</a>
        <label for="scene-name" class="text-sm font-medium">{{SCENE_LABEL}}</label>
        <input id="scene-name" value="{{SCENE_NAME_DEFAULT}}" aria-label="{{SCENE_NAME_ARIA}}"
               class="w-40 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm
                      focus:outline-none focus:ring-2 focus:ring-emerald-600" />
      </div>
    </header>

    <div class="grid grid-cols-1 gap-4 lg:grid-cols-[18rem_1fr_18rem]">
      <!-- ============ LEFT: device palette ============ -->
      <aside class="rounded-xl border border-slate-200 bg-white p-4">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-sm font-semibold">{{DEVICES_H2}}</h2>
          <button id="refresh" title="{{REFRESH_TITLE}}"
                  class="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium hover:bg-slate-200
                         focus:outline-none focus:ring-2 focus:ring-emerald-600">{{REFRESH_BUTTON}}</button>
        </div>
        <p class="mb-2 text-xs text-slate-500">{{PALETTE_HINT}}</p>

        <h3 class="mb-1 mt-3 text-xs font-semibold uppercase tracking-wide text-slate-400">{{CAMERAS_H3}}</h3>
        <ul id="cams" class="space-y-1 text-sm"></ul>
        <h3 class="mb-1 mt-4 text-xs font-semibold uppercase tracking-wide text-slate-400">{{MICROPHONES_H3}}</h3>
        <ul id="mics" class="space-y-1 text-sm"></ul>

        <div id="palette-empty" class="mt-4 hidden rounded-lg bg-amber-50 p-3 text-xs text-amber-800">
          {{PALETTE_EMPTY_LEAD}} <code>ffmpeg</code> {{PALETTE_EMPTY_TAIL}}
        </div>
      </aside>

      <!-- ============ CENTER: canvas ============ -->
      <section>
        <div class="mb-2 flex flex-wrap items-center gap-2">
          <button id="autofill"
                  class="rounded-lg bg-slate-700 px-3 py-1.5 text-sm font-semibold text-white
                         hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-600">
            {{AUTOFILL_BUTTON}}</button>
          <button id="clear"
                  class="rounded-lg bg-slate-100 px-3 py-1.5 text-sm font-semibold
                         hover:bg-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-600">
            {{CLEAR_BUTTON}}</button>
          <span class="ml-auto text-xs text-slate-500">{{DRAG_HINT}}</span>
        </div>
        <!-- The scene canvas. Camera tiles are absolutely positioned inside; the
             coordinate system is the scene's own pixel space, scaled to fit. -->
        <div id="canvas"
             class="relative w-full overflow-hidden rounded-xl border-2 border-slate-300 bg-slate-900">
          <div id="canvas-empty"
               class="absolute inset-0 flex items-center justify-center text-center text-sm text-slate-400">
            {{CANVAS_EMPTY}}
          </div>
        </div>
        <!-- Microphone meters live under the canvas (no visual footprint on it). -->
        <div id="meters" class="mt-3 space-y-2"></div>
      </section>

      <!-- ============ RIGHT: inspector + save/load ============ -->
      <aside class="rounded-xl border border-slate-200 bg-white p-4">
        <h2 class="mb-3 text-sm font-semibold">{{INSPECTOR_H2}}</h2>
        <div id="inspector" class="text-sm text-slate-500">{{INSPECTOR_EMPTY}}</div>

        <hr class="my-4 border-slate-200" />
        <h2 class="mb-2 text-sm font-semibold">{{CANVAS_SIZE_H2}}</h2>
        <div class="grid grid-cols-2 gap-2">
          <label class="text-xs">{{WIDTH_LABEL}}
            <input id="canvas-w" type="number" value="1280"
                   class="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1 text-sm" /></label>
          <label class="text-xs">{{HEIGHT_LABEL}}
            <input id="canvas-h" type="number" value="720"
                   class="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1 text-sm" /></label>
        </div>

        <hr class="my-4 border-slate-200" />
        <h2 class="mb-2 text-sm font-semibold">{{SCENE_ARTIFACT_H2}}</h2>
        <div class="flex flex-col gap-2">
          <button id="save"
                  class="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white
                         hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-600">
            {{SAVE_BUTTON}}</button>
          <label class="rounded-lg border border-slate-300 px-3 py-2 text-center text-sm font-medium
                        cursor-pointer hover:bg-slate-50 focus-within:ring-2 focus-within:ring-emerald-600">
            {{LOAD_LABEL}}
            <input id="load-file" type="file" accept=".json,application/json" class="hidden" />
          </label>
          <button id="show-json"
                  class="rounded-lg bg-slate-100 px-3 py-2 text-sm font-medium hover:bg-slate-200
                         focus:outline-none focus:ring-2 focus:ring-emerald-600">
            {{SHOW_JSON_BUTTON}}</button>
        </div>
        <span id="status" class="mt-2 block text-xs text-slate-600" role="status" aria-live="polite"></span>
        <pre id="json" class="mt-2 hidden max-h-64 overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-emerald-200"></pre>
      </aside>
    </div>
  </div>

  <script type="module">
    // Every human-readable string the script writes comes from the locale
    // file, injected as JSON — the one encoding an apostrophe cannot break
    // out of, and French copy is full of them.
    const T = {{T_JSON}};

    // ------------------------------------------------------------------ helpers
    const $ = (id) => document.getElementById(id);
    const status = (m) => { $("status").textContent = m; };
    const uid = () => (crypto.randomUUID ? crypto.randomUUID().replace(/-/g, "") : String(Math.random()).slice(2));

    // The in-memory scene. Mirrors capture_helper.scene.Scene exactly so the
    // save/load round-trip through the API is loss-free.
    const scene = { format_version: 1, name: T.sceneNameDefault, width: 1280, height: 720, sources: [] };
    let selectedId = null;                 // currently-inspected source id
    const meterTimers = new Map();         // mic id -> interval handle

    // ------------------------------------------------------------ device palette
    // Fetch the host's devices and render the clickable palette.
    async function loadDevices() {
      status(T.enumerating);
      let list = [];
      try {
        const r = await fetch("/sources");
        list = await r.json();
      } catch (e) { status(T.apiUnreachable.replace("{error}", e)); return; }
      const cams = list.filter((s) => s.kind === "camera");
      const mics = list.filter((s) => s.kind === "microphone");
      renderPalette($("cams"), cams, "camera");
      renderPalette($("mics"), mics, "microphone");
      $("palette-empty").classList.toggle("hidden", list.length > 0);
      // Named fields, not a template literal: a translator can reorder the
      // sentence instead of inheriting the order JavaScript glued it in.
      status(list.length
        ? T.found.replace("{cameras}", cams.length).replace("{mics}", mics.length)
        : T.noDevices);
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
      scene.name = $("scene-name").value || T.sceneNameDefault;
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
        img.alt = T.previewAlt.replace("{label}", s.label);
        img.className = "h-full w-full object-cover";
        img.addEventListener("error", () => {
          // No live device (headless / permission) → show a placeholder label.
          img.replaceWith(Object.assign(document.createElement("div"), {
            className: "flex h-full w-full items-center justify-center bg-slate-800 text-xs text-slate-400",
            textContent: T.noLivePreview.replace("{label}", s.label),
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
      if (!s) {
        // Built as a node rather than spliced into innerHTML: the text comes
        // from the locale file, and a translation is copy, never markup.
        box.textContent = "";
        const hint = document.createElement("span");
        hint.className = "text-slate-500";
        hint.textContent = T.inspectorEmpty;
        box.appendChild(hint);
        return;
      }
      const numField = (key, label, val) =>
        `<label class="block text-xs">${label}
           <input data-f="${key}" type="number" value="${val}"
                  class="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-sm" /></label>`;
      const isCam = s.kind === "camera";
      box.innerHTML =
        `<div class="mb-2 flex items-center justify-between">
           <span class="rounded bg-slate-100 px-2 py-0.5 text-xs font-semibold">${s.kind}</span>
           <button id="del" class="text-xs font-medium text-red-600 hover:underline">${T.removeButton}</button>
         </div>
         <label class="block text-xs">${T.labelField}
           <input data-f="label" value="${s.label}" class="mt-0.5 w-full rounded border border-slate-300 px-2 py-1 text-sm" /></label>
         <div class="mt-2 grid grid-cols-2 gap-2">
           ${isCam ? numField("x", "x", s.x) + numField("y", "y", s.y) + numField("w", "w", s.w) + numField("z", T.zField, s.z) : ""}
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
      status(T.saving);
      try {
        const r = await fetch("/scene/save", {
          method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(scene),
        });
        if (!r.ok) { status(T.saveFailed.replace("{error}", (await r.text()).slice(0, 200))); return; }
        const blob = await r.blob();
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = (scene.name || "scene") + ".scene.json";
        a.click();
        status(T.saved);
      } catch (e) { status(T.saveFailed.replace("{error}", e)); }
    });

    // Load a scene file: validate it server-side, then adopt it locally.
    $("load-file").addEventListener("change", async (e) => {
      const f = e.target.files[0]; if (!f) return;
      status(T.loading);
      try {
        const fd = new FormData(); fd.append("file", f);
        const r = await fetch("/scene/load", { method: "POST", body: fd });
        if (!r.ok) { status(T.loadFailed.replace("{error}", (await r.text()).slice(0, 200))); return; }
        adopt(await r.json());
        status(T.loaded);
      } catch (err) { status(T.loadFailed.replace("{error}", err)); }
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
      status(T.autofilling);
      try {
        const r = await fetch("/scene");   // server builds a scene from live devices
        adopt(await r.json());
        status(T.autofilled);
      } catch (e) { status(T.autofillFailed.replace("{error}", e)); }
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


def render_gui(lang: str = "") -> str:
    """Render the single-page GUI in the requested language.

    Parameters
    ----------
    lang : str
        Two-letter language code. Anything outside the locale file's
        ``meta.supported_locales`` — including the empty string — falls back
        to ``meta.default_locale``, so an unknown ``?lang=`` never 500s.

    Returns
    -------
    str
        The complete HTML document for that language.

    Examples
    --------
    >>> "<!doctype html>" in render_gui("en")
    True
    >>> render_gui("tlh") == render_gui(default_language())
    True
    """
    resolved = lang if lang in supported_languages() else default_language()
    loc = _locales()

    page = _GUI_TEMPLATE.replace("{{LANG}}", html.escape(resolved, quote=True))
    for token, key in _HTML_TOKEN_TO_KEY.items():
        # Escape every value: these land in attributes (title, aria, value,
        # href) as readily as in text nodes, and a stray quote would break out
        # of the attribute it sits in.
        value = html.escape(loc.text(_GUI_SECTION, key, resolved), quote=True)
        page = page.replace("{{" + token + "}}", value)

    # The script's strings go in as JSON rather than as substituted text: it is
    # the encoding that cannot be broken out of by an apostrophe, and French
    # copy is full of them.
    table = {name: loc.text(_GUI_SECTION, key, resolved) for name, key in _JS_NAME_TO_KEY.items()}
    return page.replace("{{T_JSON}}", json.dumps(table, ensure_ascii=False))


def __getattr__(name: str) -> str:
    """Serve ``GUI_HTML`` on first access rather than building it at import.

    The module-level constant used to BE the page, and importers still reach
    for it. Assigning it eagerly would read and parse the locale file on every
    import of this module, including in callers that never serve the GUI — and
    a module-level ``__getattr__`` only fires for names that are NOT otherwise
    defined, so the name is deliberately left unbound rather than set to a
    placeholder.
    """
    if name == "GUI_HTML":
        return render_gui()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
