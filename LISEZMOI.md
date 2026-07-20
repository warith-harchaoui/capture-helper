# Capture Helper

[🇫🇷](LISEZMOI.md) · [🇬🇧](README.md)

[![CI](https://github.com/warith-harchaoui/capture-helper/actions/workflows/ci.yml/badge.svg)](https://github.com/warith-harchaoui/capture-helper/actions/workflows/ci.yml) [![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#) [![Local-first](https://img.shields.io/badge/privacy-local--first-2f6f5e.svg)](#la-promesse)

`Capture Helper` fait partie d'une collection de bibliothèques appelée `AI Helpers`, développée pour bâtir des applications d'intelligence artificielle.

Couche **de capture caméra / microphone en forme de bibliothèque**, local-first, pour la stack AI Helpers, avec un **configurateur de scène multi-sources en direct** (GUI). Elle transforme vos caméras et microphones en direct dans les mêmes contrats array / PCM que le reste de la suite consomme — `iter_camera_frames` yield des arrays BGR uint8 `(H, W, 3)` comme `extract_frames` de [video-helper](https://github.com/warith-harchaoui/video-helper), et `iter_mic_audio` yield des `MicFrame` comme `extract_audio_stream` de [podcast-helper](https://github.com/warith-harchaoui/podcast-helper) — et vous laisse composer plusieurs sources en direct sur un canevas, les prévisualiser dans le navigateur, et enregistrer le design comme une scène JSON réutilisable que la CLI / l'API peut rejouer. Projet à ses débuts : les itérateurs de capture sont stables ; le configurateur de scène est nouveau.

[🌍 AI Helpers](https://harchaoui.org/warith/ai-helpers)

[![logo](assets/logo.png)](https://harchaoui.org/warith/ai-helpers)

## La promesse

**Local-first par conception.** capture-helper s'exécute entièrement sur votre machine ; les données caméra et microphone sont capturées et traitées localement — jamais téléversées vers un service tiers, aucune télémétrie, aucun compte, aucun verrouillage cloud. Fait partie de la suite [AI Helpers](https://github.com/warith-harchaoui/ai-helpers) : la souveraineté sur vos données grâce à l'Open Source local-first.

## Documentation

[💻 Documentation](https://harchaoui.org/warith/ai-helpers/docs/capture-helper-doc/)

[📋 Exemples](https://github.com/warith-harchaoui/capture-helper/blob/main/EXAMPLES.md)

## Fonctionnalités

Projet à ses débuts, mais voici exactement ce qui existe aujourd'hui.

**Couche de capture (contrats stables)**

- Littéral `SourceKind` (`"camera"` | `"microphone"`)
- Dict typé `Source` (kind, name, index, platform, driver)
- Dict typé `MicFrame` (miroir de [`podcast_helper.PcmFrame`](https://github.com/warith-harchaoui/podcast-helper))
- `list_sources(kind=None)` — énumération multi-plateforme des périphériques via `ffmpeg -list_devices` (macOS avfoundation / Windows dshow / Linux v4l2 + pulse)
- `pick_source(kind, *, name_substring=..., index=...)` — sélectionne le premier appareil correspondant ; lève `ValueError` si aucun ne matche
- `iter_camera_frames(source, *, width=..., height=..., output_width=..., output_height=..., fps=..., max_frames=...)` — yield **des arrays numpy BGR uint8 `(H, W, 3)`**, même contrat que `video_helper.extract_frames`
- `iter_mic_audio(source, *, target_sample_rate=16000, to_mono=True, frame_ms=20)` — itérateur async yieldant des `MicFrame`, même contrat que `podcast_helper.extract_audio_stream`
- `ffmpeg_input_args(source)` — helper bas-niveau exposé pour les utilisateurs qui veulent câbler leur propre pipeline ffmpeg

**Configurateur de scène multi-sources en direct (nouveau, additif)**

- **GUI navigateur à `GET /gui`** — énumère toutes les caméras + microphones, déposez-les sur un canevas 16:9, **prévisualisez chaque caméra en direct** via un flux MJPEG dans le navigateur, observez les **vumètres de niveau micro en direct**, glissez / arrangez les tuiles, puis **enregistrez le design comme une scène JSON réutilisable** (et rechargez-en une). Sans étape de build : JS vanilla + Tailwind CDN.
- **Modèle de scène** — dicts typés `Scene` / `SceneSource`, `new_scene(...)`, `add_source(...)`, `validate_scene(...)`, `save_scene(...)`, `load_scene(...)`, `resolve_scene_sources(...)` (mappe une scène sur les appareils de la machine courante), `scene_from_available_devices(...)`.
- **Primitives de preview live** — `snapshot_jpeg(source)` (un JPEG live), `iter_camera_jpeg(source)` (flux JPEG pour MJPEG), `mic_level(source)` (RMS / crête dBFS pour un vumètre), `frame_to_jpeg(frame)`.
- **CLI scène** — `capture-helper scene-auto` (auto-remplissage depuis les appareils), `scene-validate`, `scene-show` (rapporte comment chaque source se résout ici).
- **Endpoints HTTP scène / preview** — `GET /scene`, `POST /scene/save`, `POST /scene/load`, `GET /preview/camera.jpg`, `GET /preview/camera.mjpeg`, `GET /preview/mic-level`.

C'est un **configurateur de scène multi-sources en direct** : une mise en page visuelle de caméras / microphones en direct qui se sérialise en un artefact portable — le design devient une recette de capture headless et scriptable.

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
| **v0.1.0** | INPUT | `pick_source(...)` + `iter_camera_frames(source, ...)` + `iter_mic_audio(source, ...)` — compose avec les contrats de video-helper / podcast-helper |
| **v0.3.0** (cette release) | SCÈNES + GUI | Modèle de scène (save / load / validate / resolve), primitives de preview live (JPEG / MJPEG caméra, niveau micro), et le configurateur de scène multi-sources en direct dans le navigateur à `/gui` |
| **ensuite** | INPUT étendue | Capture d'écran / de fenêtre ; chaîne de filtres de base (noise gate, gain, scale) |
| **plus tard** | PROCESS | Mixeur multi-sources — `mix_audio([sources], levels=[...])` + `compose_video([sources], layout=...)` rejouant une scène enregistrée vers une sortie unique |

Pour un cookbook complet (chaînes d'entrée ffmpeg par OS, capture d'instantané, preview live, save/load de scène, câblage ASR / VAD), voir [📋 EXAMPLES.md](EXAMPLES.md). Pour le catalogue exhaustif de déclencheurs (et le skill Claude / OpenCode), voir [📋 TRIGGERS.md](TRIGGERS.md) et [`skills/capture-helper/`](https://github.com/warith-harchaoui/capture-helper/tree/main/skills/capture-helper).

## Exposition multi-surface

`capture-helper` expose les mêmes capacités à travers **six
surfaces**, pour qu'elle se branche là où vous travaillez déjà —
sans réécriture.

| Surface | Installation | Point d'entrée | Cas d'usage |
| --- | --- | --- | --- |
| **Bibliothèque Python** | `pip install capture-helper` | `import capture_helper as ch` | Notebooks, scripts, autres AI Helpers |
| **CLI argparse** | *(sans extra)* | `capture-helper …` | Shells, cron, CI, CMD de container |
| **CLI click** | extra `[cli]` | `capture-helper-click …` | Utilisateurs avec stack click-native (complétion, `--help` colorée) |
| **HTTP FastAPI** | extra `[api]` | `uvicorn capture_helper.api:app` | Service derrière un reverse-proxy, clients JSON / multipart |
| **GUI navigateur** | extra `[api]` | `GET /gui` | Configurateur de scène multi-sources en direct (preview + arrangement + sauvegarde) |
| **Tools MCP** | extras `[api,mcp]` | `capture-helper-mcp` | Agents LLM (Claude Desktop, clients MCP custom) |

```bash
# CLI (argparse — toujours disponible)
capture-helper list-sources
capture-helper pick-source --kind camera --name FaceTime
capture-helper capture-mic --output mic.wav --seconds 3

# CLI (jumeau click — mêmes sous-commandes)
capture-helper-click list-sources
capture-helper-click capture-camera --output-dir frames/ \
    --output-width 640 --output-height 360 --max-frames 30

# Surface HTTP
uvicorn capture_helper.api:app --host 0.0.0.0 --port 8000
curl http://localhost:8000/sources
curl -o frames.zip \
    'http://localhost:8000/capture/camera?output_width=320&output_height=240&max_frames=10'

# GUI navigateur — configurateur de scène multi-sources en direct
uvicorn capture_helper.api:app --port 8000
# ouvrez http://localhost:8000/gui  (ou juste http://localhost:8000/)

# Surface MCP (FastAPI + fastapi-mcp)
capture-helper-mcp   # sert les routes HTTP + l'endpoint MCP sur :8000

# Docker (embarque FastAPI + MCP + GUI par défaut)
docker build -t capture-helper .
docker run --rm -p 8000:8000 capture-helper
```

Le **GUI** à `/gui` est le configurateur de scène multi-sources en direct : il énumère vos caméras / microphones, prévisualise chaque caméra en direct (MJPEG) et chaque micro (vumètre), vous laisse les arranger sur un canevas, et enregistre le design comme un `.scene.json` réutilisable que la CLI / l'API peut rejouer. Voir [📋 GUI.md](GUI.md). Pour un comparatif face à OpenCV / PyAV / sounddevice / FFmpeg CLI / GStreamer et aux GUI de streaming de bureau, voir [📋 LANDSCAPE.md](LANDSCAPE.md).

## Installation

**Prérequis** — **Python 3.10–3.13** et **git**, **ffmpeg**, **PortAudio**, multiplateforme :

- 🍎 **macOS** ([Homebrew](https://brew.sh)) : `brew install python git ffmpeg portaudio`
- 🐧 **Ubuntu/Debian** : `sudo apt update && sudo apt install -y python3 python3-pip git ffmpeg portaudio19-dev`
- 🪟 **Windows** (PowerShell) : `winget install Python.Python.3.12 Git.Git Gyan.FFmpeg` (PortAudio est inclus dans les wheels Python)

Nous recommandons d'utiliser des environnements Python. Consultez ce lien si vous ne savez pas comment en configurer un : [🥸 Astuces techniques](https://harchaoui.org/warith/4ml/#install).

Il vous faut `ffmpeg` dans le PATH pour que l'énumération de périphériques et la capture live retournent quelque chose.

### Depuis PyPI (recommandé)

```bash
# Couche INPUT de base (list/pick sources, itérateurs caméra + micro)
pip install capture-helper

# Surfaces optionnelles
pip install "capture-helper[cli]"       # jumeau CLI click
pip install "capture-helper[api]"       # surface HTTP FastAPI
pip install "capture-helper[api,mcp]"   # tools MCP au-dessus de FastAPI
```

### Depuis les sources (sans PyPI)

```bash
# Couche INPUT de base
pip install "git+https://github.com/warith-harchaoui/capture-helper.git@v0.3.0"

# Surfaces optionnelles
pip install "capture-helper[cli] @ git+https://github.com/warith-harchaoui/capture-helper.git@v0.3.0"
pip install "capture-helper[api] @ git+https://github.com/warith-harchaoui/capture-helper.git@v0.3.0"
pip install "capture-helper[api,mcp] @ git+https://github.com/warith-harchaoui/capture-helper.git@v0.3.0"
```

## Auteur

 - [Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui)

## Remerciements

Remerciements chaleureux à [Mohamed Chelali](https://mchelali.github.io) et [Bachir Zerroug](https://www.linkedin.com/in/bachirzerroug) pour nos échanges fructueux.

## Licence

Ce projet est distribué sous licence BSD-3-Clause — voir le fichier [LICENSE](LICENSE) pour les détails.
