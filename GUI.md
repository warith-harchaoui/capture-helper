# GUI — Capture Helper

> A design plan, not a CLI mirror. The CLI already handles
> "enumerate devices, snapshot frames, record N seconds". A GUI must
> go further — otherwise why build one? This document lays out an
> ambitious, opinionated visual product for the OBS-inspired
> capture / mix / publish workflow that Capture Helper aims at.

## North star

> **A live device wall where every camera, microphone and screen on
> the machine has a self-updating tile — and any tile can be
> promoted to a "program" bus with one keystroke.**

Capture work is inherently spatial (which device is in what corner?)
and temporal (is this mic clipping right now?). The CLI cannot show
you either. The GUI's job is to make the **hardware topology and its
live health visible**, plus provide a **cueing model** that OBS users
already know — without dragging in OBS's scene-graph complexity.

## Three surfaces, one product

### 1. Device Wall *(primary surface)*

- Auto-populated grid of tiles: one per `Source` returned by
  `list_sources()`. Tiles are grouped by kind (cameras row,
  microphones row, screens row once v0.2.0 ships).
- Each camera tile shows a **live 5 fps preview**, the OS name,
  the driver (`avfoundation` / `v4l2` / `dshow` / …) and the last-
  observed resolution / frame rate. Ffmpeg latency is annotated
  live from the frame timestamp delta.
- Each microphone tile shows a **live VU meter + 200 ms
  waveform**, plus a peak-hold LED. Clipping is a red border
  around the tile. Nothing subtle.
- One toggle per tile: **"Cue"** (green outline) → sends the
  source to the preview bus. Same tile: **"Program"** (red
  outline, shortcut `Enter`) → promotes it to the live bus. This
  matches the mixer / vision-mixer metaphor and is instantly
  familiar to anyone who has used a hardware switcher.

### 2. Program Bus + Comparator

Two full-size tiles at the top: **PGM** (what your recording /
stream would show now) and **PVW** (what you are cueing). Two
bindings ripped straight from broadcast:

- `Space` — **T-bar cut** (instant swap PVW ↔ PGM).
- Hold `Tab` — **auto-mix crossfade** at the configured speed
  (default 500 ms). Everyone with a live-production instinct
  reaches for this within 20 seconds.

Below PGM: a **rolling 30-second waveform of the current program
audio** with a moving RMS overlay. Downstream we intend to hook
that into `podcast-helper`'s VAD so speech / silence segments
appear as coloured bands underneath.

### 3. Snapshot & Record Panel

- **Snapshot** button: writes the current PGM frame as a PNG to
  the project folder. Keyboard: `S`.
- **Record**: same shortcut set as OBS — `Ctrl+R` to start / stop.
  On stop the panel shows the file, its duration and a **one-
  click "Send to video-helper / podcast-helper" chip** — the whole
  point of Capture Helper is being a first-class producer for the
  rest of the AI Helpers suite, so a GUI must materialise that
  connection.
- Recordings land in a per-day folder with a `session.json` file
  that lists every device that was live during the session, at
  the resolutions / sample rates observed. Reproducibility.

## Design principles

- **Health is visible or it isn't there.** Every device tile
  shows enough state to know at a glance if the pipeline is
  healthy — no hidden warnings, no console logs.
- **Broadcast semantics, not DAW semantics.** PGM / PVW / T-bar /
  auto-mix are the mental model. We do not ship a timeline
  editor.
- **Files, not memory blobs.** Recordings and snapshots write
  through the same `capture_helper` iterators the CLI uses — the
  files are byte-identical regardless of surface.
- **Keyboard first, mouse second.** Every action has a shortcut.
  Muscle memory from OBS / vMix / Blackmagic ATEM works out of
  the box.
- **Colorblind-safe by construction.** All state uses shape +
  colour + text, never colour alone (see the companion
  `front-colors` audit skill).
- **Never mutate the OS driver stack.** Enumeration and capture
  are read-only from the OS's perspective — no ffmpeg command
  runs "just to see" outside of a user-initiated tile.

## What we deliberately don't do

- **No scene tree.** OBS has one — we do not compete with it.
  Layouts land as a v0.3.0 library primitive (`compose_video`)
  and get a single "layout picker" in the GUI, not a nested
  editor.
- **No plugin marketplace.** Everything is code in this repo.
- **No cloud lock-in.** Everything runs against the local
  FastAPI server the container already ships. GUI is a thin JS
  client that only talks to `localhost`.

## Stack

- Front end: TypeScript + Svelte 5 + a `<canvas>` for camera
  previews + WebAudio for VU meters. No React — matches the
  `front-ui` companion skill's stack.
- Back end: the FastAPI app already exists
  (`capture_helper.api`) and covers 100 % of the current
  operations. GUI is a client only.
- Session format: JSON, versioned, human-diffable.

## Milestones

| Milestone | What ships | Why first |
| --- | --- | --- |
| M0 | Device Wall, cameras only. Live preview + resolution readout. | Prove the tile metaphor before scaling to mics / screens. |
| M1 | Mic tiles with VU + waveform. Snapshot / Record panel. | Rounds out the v0.1.0 library surface. |
| M2 | PGM / PVW + T-bar / auto-mix. `Send to video-helper` chip. | This is the "why a GUI" moment — hands-on live cueing. |
| M3 | Screen / window tiles (once v0.2.0 lands the library primitive). | Feature parity with OBS scenes. |
| M4 | Layout picker + `emit_to_youtube_live` button (once v0.4.0 lands the publish layer). | One-click go-live for solo streamers. |

## Non-goals (recorded so we do not drift)

- Not a full production switcher (Blackmagic ATEM already exists).
- Not a hosted SaaS.
- Not a replacement for OBS scene collections.

## Success metric

> A user who owns a webcam, a USB mic, and one screen can open the
> app, hit `Enter` twice to promote their camera and mic to
> program, hit `Ctrl+R`, talk for 30 seconds, and drop the
> resulting `.mp4` + `.wav` straight into `video-helper` /
> `podcast-helper` for downstream processing — without opening a
> terminal.

If we ship that, we win.
