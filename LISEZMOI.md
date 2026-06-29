# Capture Helper

[🇫🇷](LISEZMOI.md) · [🇬🇧](README.md)

[![CI](https://github.com/warith-harchaoui/capture-helper/actions/workflows/ci.yml/badge.svg)](https://github.com/warith-harchaoui/capture-helper/actions/workflows/ci.yml) [![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#)

`Capture Helper` fait partie d'une collection de bibliothèques appelée `AI Helpers`, développée pour bâtir des applications d'intelligence artificielle.

Couche **inspirée d'OBS** (sans GUI) pour la capture + le traitement + la diffusion dans la stack AI Helpers. En forme de bibliothèque : sources caméra / microphone / écran / fenêtre / audio applicatif multiplateformes, chaînes de filtres composables, mixage multi-sources, et primitives emit-to-publish pour YouTube live / Twitch RTMP, HLS, et Icecast — conçue pour se brancher dans [video-helper](https://github.com/warith-harchaoui/video-helper) et [podcast-helper](https://github.com/warith-harchaoui/podcast-helper) au contrat frame / PCM en aval.

[🌍 AI Helpers](https://harchaoui.org/warith/ai-helpers)

[![logo](assets/logo.png)](https://harchaoui.org/warith/ai-helpers)

## Statut — couche INPUT v0.1.0

Ce qui marche aujourd'hui :

- Littéral `SourceKind` (`"camera"` | `"microphone"`)
- Dict typé `Source` (kind, name, index, platform, driver)
- Dict typé `MicFrame` (miroir de [`podcast_helper.PcmFrame`](https://github.com/warith-harchaoui/podcast-helper))
- `list_sources(kind=None)` — énumération multi-plateforme des périphériques via `ffmpeg -list_devices` (macOS avfoundation / Windows dshow / Linux v4l2 + pulse)
- `pick_source(kind, *, name_substring=..., index=...)` — sélectionne le premier appareil correspondant ; lève `ValueError` si aucun ne matche
- `iter_camera_frames(source, *, width=..., height=..., output_width=..., output_height=..., fps=..., max_frames=...)` — yield **des arrays numpy BGR uint8 `(H, W, 3)`**, même contrat que `video_helper.extract_frames`
- `iter_mic_audio(source, *, target_sample_rate=16000, to_mono=True, frame_ms=20)` — itérateur async yieldant des `MicFrame`, même contrat que `podcast_helper.extract_audio_stream`
- `ffmpeg_input_args(source)` — helper bas-niveau exposé pour les utilisateurs qui veulent câbler leur propre pipeline ffmpeg

```python
import asyncio
import capture_helper as ch

# Énumérer les périphériques disponibles
for s in ch.list_sources():
    print(f"{s['kind']:10s} [{s['index']}] {s['name']:40s} (driver={s['driver']})")
    # camera     [0] FaceTime HD Camera                       (driver=avfoundation)
    # microphone [0] Built-in Microphone                      (driver=avfoundation)

# Caméra → frames numpy BGR (drop-in pour video_helper.extract_frames)
cam = ch.pick_source("camera")
for frame in ch.iter_camera_frames(cam, output_width=640, output_height=360,
                                   fps=30, max_frames=300):
    # frame.shape == (360, 640, 3), dtype uint8, BGR.
    do_something(frame)

# Microphone → stream PCM async (drop-in pour podcast_helper.extract_audio_stream)
async def listen():
    mic = ch.pick_source("microphone")
    async for f in ch.iter_mic_audio(mic, target_sample_rate=16000,
                                     to_mono=True, frame_ms=20):
        # f["pcm"].shape == (320,) — 20ms @ 16kHz mono.
        await asr.feed(f["pcm"])
asyncio.run(listen())
```

## Roadmap

| Version | Couche | Périmètre |
|---|---|---|
| v0.0.1 | Squelette INPUT | `list_sources` + types |
| **v0.1.0** (cette release) | INPUT | `pick_source(...)` + `iter_camera_frames(source, ...)` + `iter_mic_audio(source, ...)` — compose avec les contrats de video-helper / podcast-helper |
| **v0.2.0** | INPUT étendue | Capture d'écran / de fenêtre ; chaîne de filtres de base (noise gate, gain, scale) |
| **v0.3.0** | PROCESS | Scènes / mixeur — `mix_audio([sources], levels=[...])` + `compose_video([sources], layout=...)` |
| **v0.4.0** | PUBLISH | `emit_to_youtube_live(...)`, `emit_to_twitch_live(...)`, `emit_to_rtmp(...)`, `emit_to_hls(...)`, `emit_audio_to_icecast(...)` |
| **v0.5.0** | OUTPUT virtuel | `output_to_virtual_camera(...)` (pyvirtualcam etc.), `output_to_virtual_mic(...)` |
| **v0.6.0** | Intégration OBS | Client OBS WebSocket (réagir aux événements scène / stream) |

Pour un cookbook complet (chaînes d'entrée ffmpeg par OS, capture d'instantané, preview live, câblage ASR / VAD), voir [📋 EXAMPLES.md](EXAMPLES.md).

## Installation

```bash
pip install --force-reinstall --no-cache-dir \
  git+https://github.com/warith-harchaoui/capture-helper.git@v0.1.0
```

Il vous faut `ffmpeg` dans le PATH pour que l'énumération de périphériques retourne quelque chose :

- macOS 🍎 : `brew install ffmpeg`

  (installez `brew` grâce à [brew.sh](https://brew.sh/))
- Ubuntu 🐧 : `sudo apt install ffmpeg`
- Windows 🪟 : récupérer un build sur [ffmpeg.org/download.html](https://ffmpeg.org/download.html) et l'ajouter au `PATH`.

# Auteur
 - [Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui)

# Remerciements
Remerciements chaleureux à [Mohamed Chelali](https://mchelali.github.io) et [Bachir Zerroug](https://www.linkedin.com/in/bachirzerroug) pour nos échanges fructueux.
