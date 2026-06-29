# Capture Helper

> 🌐 English version: [README.md](README.md)

`Capture Helper` fait partie d'une collection de bibliothèques appelée `AI Helpers`, développée pour bâtir des applications d'intelligence artificielle.

Couche **inspirée d'OBS** (sans GUI) pour la capture + le traitement + la diffusion dans la stack AI Helpers. En forme de bibliothèque : sources caméra / microphone / écran / fenêtre / audio applicatif multiplateformes, chaînes de filtres composables, mixage multi-sources, et primitives emit-to-publish pour YouTube live / Twitch RTMP, HLS, et Icecast — conçue pour se brancher dans [video-helper](https://github.com/warith-harchaoui/video-helper) et [podcast-helper](https://github.com/warith-harchaoui/podcast-helper) au contrat frame / PCM en aval.

[🕸️ AI Helpers](https://harchaoui.org/warith/ai-helpers)

[![logo](assets/logo.png)](https://harchaoui.org/warith/ai-helpers)

## Statut — squelette v0.0.1

Cette release est **un squelette**. Elle expose les types publics et l'énumération de périphériques de base. Le gros morceau (itération par source, chaînes de filtres, mixeur, couche de diffusion) arrive dans les releases suivantes.

Ce qui marche aujourd'hui :

- Littéral `SourceKind` (`"camera"` | `"microphone"`)
- Dict typé `Source` (kind, name, index, platform, driver)
- `list_sources(kind=None)` — énumération multi-plateforme des périphériques via `ffmpeg -list_devices` (macOS avfoundation / Windows dshow / Linux v4l2 + pulse)

```python
from capture_helper import list_sources

for s in list_sources("microphone"):
    print(f"[{s['index']}] {s['name']} (driver={s['driver']})")
```

## Roadmap

| Version | Couche | Périmètre |
|---|---|---|
| **v0.0.1** (cette release) | Squelette INPUT | `list_sources` + types |
| **v0.1.0** | INPUT | `pick_source(...)` + `iter_camera_frames(source, ...)` + `iter_mic_audio(source, ...)` — compose avec les contrats de video-helper / podcast-helper |
| **v0.2.0** | INPUT étendue | Capture d'écran / de fenêtre ; chaîne de filtres de base (noise gate, gain, scale) |
| **v0.3.0** | PROCESS | Scènes / mixeur — `mix_audio([sources], levels=[...])` + `compose_video([sources], layout=...)` |
| **v0.4.0** | PUBLISH | `emit_to_youtube_live(...)`, `emit_to_twitch_live(...)`, `emit_to_rtmp(...)`, `emit_to_hls(...)`, `emit_audio_to_icecast(...)` |
| **v0.5.0** | OUTPUT virtuel | `output_to_virtual_camera(...)` (pyvirtualcam etc.), `output_to_virtual_mic(...)` |
| **v0.6.0** | Intégration OBS | Client OBS WebSocket (réagir aux événements scène / stream) |

## Installation

```bash
pip install --force-reinstall --no-cache-dir \
  git+https://github.com/warith-harchaoui/capture-helper.git@v0.0.1
```

Il vous faut `ffmpeg` dans le PATH pour que l'énumération de périphériques retourne quelque chose :

- macOS 🍎 : `brew install ffmpeg`
- Ubuntu 🐧 : `sudo apt install ffmpeg`
- Windows 🪟 : récupérer un build sur [ffmpeg.org/download.html](https://ffmpeg.org/download.html) et l'ajouter au `PATH`.

# Auteur
 - [Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui)

# Remerciements
Special thanks to [Mohamed Chelali](https://mchelali.github.io) and [Bachir Zerroug](https://www.linkedin.com/in/bachirzerroug) for fruitful discussions.
