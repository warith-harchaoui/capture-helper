# Capture Helper Examples

Practical recipes for `capture-helper` v0.0.1 — currently a scaffold
exposing **cross-platform device enumeration**. The richer iter / mix /
publish layers land in subsequent releases — see the README roadmap.

Every snippet assumes:

```python
import capture_helper as ch
```

and that `ffmpeg` is on PATH (`brew install ffmpeg` on macOS — install
`brew` thanks to [brew.sh](https://brew.sh/); `sudo apt install ffmpeg`
on Linux; a Windows build added to `PATH`).

---

## Table of Contents

1. [Setup](#setup)
2. [List all available sources](#list-all-available-sources)
3. [Filter by kind (camera / microphone)](#filter-by-kind-camera--microphone)
4. [Inspect a `Source` typed dict](#inspect-a-source-typed-dict)
5. [Build the per-OS ffmpeg input string (preview of v0.1.0)](#build-the-per-os-ffmpeg-input-string-preview-of-v010)
6. [Roadmap — what each version unlocks](#roadmap--what-each-version-unlocks)

---

## Setup

```bash
pip install --force-reinstall --no-cache-dir \
    git+https://github.com/warith-harchaoui/capture-helper.git@v0.0.1
```

The `list_sources` call shells out to `ffmpeg -list_devices` and parses
the stderr. If `ffmpeg` is missing, the call returns `[]` rather than
raising — handy for "is this machine capture-ready?" probes.

## List all available sources

```python
for s in ch.list_sources():
    print(f"{s['kind']:10s} [{s['index']}] {s['name']:40s} (driver={s['driver']})")
    # camera     [0] FaceTime HD Camera                       (driver=avfoundation)
    # camera     [1] iPhone Camera                            (driver=avfoundation)
    # microphone [0] Built-in Microphone                      (driver=avfoundation)
    # microphone [1] BlackHole 16ch                           (driver=avfoundation)
```

(Typical output on macOS with avfoundation.)

## Filter by kind (camera / microphone)

```python
for cam in ch.list_sources("camera"):
    print(cam["name"])
    # FaceTime HD Camera
    # iPhone Camera

for mic in ch.list_sources("microphone"):
    print(mic["name"])
    # Built-in Microphone
    # BlackHole 16ch
```

`list_sources` returns `[]` on platforms not yet covered (currently
darwin / linux / windows are supported); never raises.

## Inspect a `Source` typed dict

```python
from capture_helper import Source, SourceKind  # importable for downstream typing

sources: list[Source] = ch.list_sources()
for s in sources:
    print(s)
    # {'kind': 'camera', 'name': 'FaceTime HD Camera', 'index': 0,
    #  'platform': 'darwin', 'driver': 'avfoundation'}
    # (schema: kind ∈ {"camera", "microphone"}; driver ∈ {"avfoundation",
    #  "v4l2", "dshow", "pulse", "alsa"}; platform ∈ {"darwin", "linux",
    #  "windows"}.)
```

The `driver` field tells you the ffmpeg input format flag to use
downstream — `-f avfoundation` / `-f v4l2` / `-f dshow` / `-f pulse`.

## Build the per-OS ffmpeg input string (preview of v0.1.0)

In v0.0.1 you still build the ffmpeg command yourself. The pattern that
v0.1.0's `iter_camera_frames` / `iter_mic_audio` will encapsulate:

```python
import shlex, subprocess

def ffmpeg_input_for(source):
    if source["driver"] == "avfoundation":
        # Combined video/audio devices are addressed as "vidx:aidx".
        return ["-f", "avfoundation", "-i", f"{source['index']}:none"] \
            if source["kind"] == "camera" \
            else ["-f", "avfoundation", "-i", f"none:{source['index']}"]
    if source["driver"] == "v4l2":
        return ["-f", "v4l2", "-i", source["name"]]
    if source["driver"] == "dshow":
        kind_label = "video" if source["kind"] == "camera" else "audio"
        return ["-f", "dshow", "-i", f"{kind_label}={source['name']}"]
    if source["driver"] == "pulse":
        return ["-f", "pulse", "-i", source["name"]]
    raise ValueError(f"Unsupported driver: {source['driver']!r}")

cam = ch.list_sources("camera")[0]
cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", *ffmpeg_input_for(cam),
       "-frames:v", "1", "snapshot.png"]
subprocess.run(cmd, check=True)
print("Saved snapshot.png from", cam["name"])
# Saved snapshot.png from FaceTime HD Camera
```

Once v0.1.0 ships, the equivalent becomes:

```python
# v0.1.0 — not yet released, design preview
src = ch.pick_source("camera")            # picks the first available
frame = next(ch.iter_camera_frames(src))  # numpy BGR uint8 (H, W, 3)
```

## Roadmap — what each version unlocks

| Version | Layer | New capability |
|---|---|---|
| **v0.0.1** (this) | INPUT scaffold | `list_sources` + types |
| v0.1.0 | INPUT | `pick_source(...)`, `iter_camera_frames(...)`, `iter_mic_audio(...)` — composes with video-helper / podcast-helper |
| v0.2.0 | INPUT extended | Screen / window capture + basic filter chain (noise gate, gain, scale) |
| v0.3.0 | PROCESS | `mix_audio([sources], levels=[...])`, `compose_video([sources], layout=...)` |
| v0.4.0 | PUBLISH | `emit_to_youtube_live`, `emit_to_twitch_live`, `emit_to_rtmp`, `emit_to_hls`, `emit_audio_to_icecast` |
| v0.5.0 | OUTPUT virtual | `output_to_virtual_camera`, `output_to_virtual_mic` |
| v0.6.0 | OBS integration | OBS WebSocket client (react to scene / stream events) |
