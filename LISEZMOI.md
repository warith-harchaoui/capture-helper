# Capture Helper

[🇫🇷](https://github.com/warith-harchaoui/capture-helper/blob/main/LISEZMOI.md) · [🇬🇧](https://github.com/warith-harchaoui/capture-helper/blob/main/README.md)

[![CI](https://github.com/warith-harchaoui/capture-helper/actions/workflows/ci.yml/badge.svg)](https://github.com/warith-harchaoui/capture-helper/actions/workflows/ci.yml) [![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://github.com/warith-harchaoui/capture-helper/blob/main/LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#) [![Local-first](https://img.shields.io/badge/privacy-local--first-2f6f5e.svg)](#la-promesse)

`Capture Helper` fait partie d'une collection de bibliothèques appelée `AI Helpers`, développée pour bâtir des applications d'intelligence artificielle.

Couche de capture caméra et microphone sous forme de bibliothèque, local-first, pour la suite AI Helpers, avec un configurateur de scène multi-sources en direct (GUI). Elle expose vos caméras et micros en direct dans les mêmes contrats array et PCM que le reste de la suite : `iter_camera_frames` produit des tableaux BGR uint8 `(H, W, 3)` comme `extract_frames` de [video-helper](https://github.com/warith-harchaoui/video-helper) ; `iter_mic_audio` produit des `MicFrame` comme `extract_audio_stream` de [podcast-helper](https://github.com/warith-harchaoui/podcast-helper). Vous pouvez aussi composer plusieurs sources en direct sur un canevas, les prévisualiser dans le navigateur, puis enregistrer le tout comme une scène JSON que la CLI ou l'API rejoue à l'identique. Les itérateurs de capture forment le socle stable ; le configurateur de scène, ajouté plus récemment, complète la boîte à outils.

[🌍 AI Helpers](https://harchaoui.org/warith/ai-helpers)

[![logo](https://raw.githubusercontent.com/warith-harchaoui/capture-helper/main/assets/logo.png)](https://harchaoui.org/warith/ai-helpers)

## La promesse

**Local-first par conception.** capture-helper s'exécute entièrement sur votre machine : les données caméra et micro sont capturées et traitées en local, jamais envoyées vers un service tiers, sans télémétrie, sans compte, sans verrouillage cloud. Fait partie de la suite [AI Helpers](https://github.com/warith-harchaoui/ai-helpers) : la souveraineté sur vos données grâce à l'open source local-first.

## Documentation

[💻 Documentation](https://harchaoui.org/warith/ai-helpers/docs/capture-helper-doc/)

[🗺️ Paysage](https://github.com/warith-harchaoui/capture-helper/blob/main/PAYSAGE.md)

[📋 Exemples](https://github.com/warith-harchaoui/capture-helper/blob/main/EXEMPLES.md)

## Fonctionnalités

Voici précisément ce qui existe aujourd'hui.

**Couche de capture (contrats stables)**

- Littéral `SourceKind` (`"camera"` | `"microphone"`)
- Dict typé `Source` (kind, name, index, platform, driver)
- Dict typé `MicFrame`, miroir de [`podcast_helper.PcmFrame`](https://github.com/warith-harchaoui/podcast-helper)
- `list_sources(kind=None)` : énumération multiplateforme des périphériques via `ffmpeg -list_devices` (macOS avfoundation, Windows dshow, Linux v4l2 + pulse)
- `pick_source(kind, *, name_substring=..., index=...)` : sélectionne le premier appareil correspondant, lève `ValueError` si aucun ne correspond
- `iter_camera_frames(source, *, width=..., height=..., output_width=..., output_height=..., fps=..., max_frames=...)` : produit **des tableaux numpy BGR uint8 `(H, W, 3)`**, le même contrat que `video_helper.extract_frames`
- `iter_mic_audio(source, *, target_sample_rate=16000, to_mono=True, frame_ms=20)` : itérateur asynchrone produisant des `MicFrame`, le même contrat que `podcast_helper.extract_audio_stream`
- `ffmpeg_input_args(source)` : utilitaire bas niveau exposé pour qui veut câbler son propre pipeline ffmpeg

**Configurateur de scène multi-sources en direct (nouveau, additif)**

- **GUI navigateur à `GET /gui`** : énumère toutes les caméras et tous les micros, déposez-les sur un canevas 16:9, **prévisualisez chaque caméra en direct** via un flux MJPEG, suivez les **vumètres de niveau micro en direct**, glissez et arrangez les tuiles, puis **enregistrez le tout comme une scène JSON réutilisable** (et rechargez-en une). Sans étape de build : JS vanilla + Tailwind CDN.
- **Modèle de scène** : dicts typés `Scene` / `SceneSource`, `new_scene(...)`, `add_source(...)`, `validate_scene(...)`, `save_scene(...)`, `load_scene(...)`, `resolve_scene_sources(...)` (mappe une scène sur les appareils de la machine courante), `scene_from_available_devices(...)`.
- **Primitives de prévisualisation en direct** : `snapshot_jpeg(source)` (un JPEG live), `iter_camera_jpeg(source)` (flux JPEG pour MJPEG), `mic_level(source)` (RMS ou crête dBFS pour un vumètre), `frame_to_jpeg(frame)`.
- **CLI de scène** : `capture-helper scene-auto` (remplissage automatique depuis les appareils), `scene-validate`, `scene-show` (rapporte comment chaque source se résout ici).
- **Points d'entrée HTTP scène et prévisualisation** : `GET /scene`, `POST /scene/save`, `POST /scene/load`, `GET /preview/camera.jpg`, `GET /preview/camera.mjpeg`, `GET /preview/mic-level`.

C'est un configurateur de scène multi-sources en direct au sens plein du terme : une mise en page visuelle de caméras et de micros qui se sérialise en artefact portable, si bien que la mise en page elle-même devient une recette de capture headless et scriptable.

```python
import asyncio
import capture_helper as ch

# Énumérer les périphériques disponibles
for s in ch.list_sources():
    print(f"{s['kind']:10s} [{s['index']}] {s['name']:40s} (driver={s['driver']})")
    # camera     [0] FaceTime HD Camera                       (driver=avfoundation)
    # microphone [0] Built-in Microphone                      (driver=avfoundation)

# Caméra → frames numpy BGR (compatible avec video_helper.extract_frames)
cam = ch.pick_source("camera")
for frame in ch.iter_camera_frames(cam, output_width=640, output_height=360,
                                   fps=30, max_frames=300):
    # frame.shape == (360, 640, 3), dtype uint8, BGR.
    do_something(frame)

# Microphone → flux PCM asynchrone (compatible avec podcast_helper.extract_audio_stream)
async def listen():
    mic = ch.pick_source("microphone")
    async for f in ch.iter_mic_audio(mic, target_sample_rate=16000,
                                     to_mono=True, frame_ms=20):
        # f["pcm"].shape == (320,), 20 ms d'audio à 16 kHz mono.
        await asr.feed(f["pcm"])
asyncio.run(listen())
```

## Installation

**Prérequis** : **Python 3.10-3.13**, **git**, **ffmpeg**, **PortAudio**, multiplateforme :

- 🍎 **macOS** ([Homebrew](https://brew.sh)) : `brew install python git ffmpeg portaudio`
- 🐧 **Ubuntu/Debian** : `sudo apt update && sudo apt install -y python3 python3-pip git ffmpeg portaudio19-dev`
- 🪟 **Windows** (PowerShell) : `winget install Python.Python.3.12 Git.Git Gyan.FFmpeg` (PortAudio est inclus dans les wheels Python)

Nous recommandons de travailler dans un environnement Python dédié. Si vous ne savez pas encore comment en créer un : [🥸 Astuces techniques](https://harchaoui.org/warith/4ml/#install).

`ffmpeg` doit être dans le PATH pour que l'énumération des périphériques et la capture en direct renvoient quelque chose.

### Depuis PyPI (recommandé)

```bash
# Couche INPUT de base (list/pick sources, itérateurs caméra + micro)
pip install capture-helper

# Surfaces optionnelles
pip install "capture-helper[cli]"       # jumeau CLI click
pip install "capture-helper[api]"       # surface HTTP FastAPI
```

### Depuis les sources (sans PyPI)

```bash
# Couche INPUT de base
pip install capture-helper

# Surfaces optionnelles
pip install "capture-helper[cli]"
pip install "capture-helper[api]"
```

## Feuille de route

| Version | Couche | Périmètre |
|---|---|---|
| v0.0.1 | Squelette INPUT | `list_sources` + types |
| **v0.1.0** | INPUT | `pick_source(...)`, `iter_camera_frames(source, ...)`, `iter_mic_audio(source, ...)` ; compose avec les contrats de video-helper et podcast-helper |
| **v0.3.0** (cette version) | SCÈNES + GUI | Modèle de scène (save / load / validate / resolve), primitives de prévisualisation en direct (JPEG / MJPEG caméra, niveau micro), configurateur de scène multi-sources en direct dans le navigateur à `/gui` |
| **ensuite** | INPUT étendue | Capture d'écran ou de fenêtre ; chaîne de filtres de base (porte de bruit, gain, redimensionnement) |
| **plus tard** | PROCESS | Mixeur multi-sources : `mix_audio([sources], levels=[...])` + `compose_video([sources], layout=...)`, rejouant une scène enregistrée vers une sortie unique |

Pour un cookbook complet (chaînes d'entrée ffmpeg par système d'exploitation, capture d'instantané, prévisualisation en direct, sauvegarde et chargement de scène, câblage ASR / VAD), voir [📋 EXAMPLES.md](https://github.com/warith-harchaoui/capture-helper/blob/main/EXAMPLES.md). Pour le catalogue exhaustif de déclencheurs, voir [📋 TRIGGERS.md](https://github.com/warith-harchaoui/capture-helper/blob/main/TRIGGERS.md).

## Exposition multi-surface

`capture-helper` expose les mêmes capacités à travers **six surfaces**, pour se brancher là où vous travaillez déjà, sans réécriture.

| Surface | Installation | Point d'entrée | Cas d'usage |
| --- | --- | --- | --- |
| **Bibliothèque Python** | `pip install capture-helper` | `import capture_helper as ch` | Notebooks, scripts, autres AI Helpers |
| **CLI argparse** | *(sans extra)* | `capture-helper …` | Shells, cron, CI, CMD de conteneur |
| **CLI click** | extra `[cli]` | `capture-helper-click …` | Utilisateurs d'une pile click-native (complétion, `--help` colorée) |
| **HTTP FastAPI** | extra `[api]` | `uvicorn capture_helper.api:app` | Service derrière un reverse-proxy, clients JSON ou multipart |
| **GUI navigateur** | extra `[api]` | `GET /gui` | Configurateur de scène multi-sources en direct (prévisualisation, arrangement, sauvegarde) |
| **MCP** | extra `[mcp]` | `capture-helper-mcp` | Tout hôte agentique compatible MCP (même app FastAPI, point d'entrée `/mcp`) |

```bash
# CLI (argparse, toujours disponible)
capture-helper list-sources
capture-helper pick-source --kind camera --name FaceTime
capture-helper capture-mic --output mic.wav --seconds 3

# CLI (jumeau click, mêmes sous-commandes)
capture-helper-click list-sources
capture-helper-click capture-camera --output-dir frames/ \
    --output-width 640 --output-height 360 --max-frames 30

# Surface HTTP
uvicorn capture_helper.api:app --host 0.0.0.0 --port 8000
curl http://localhost:8000/sources
curl -o frames.zip \
    'http://localhost:8000/capture/camera?output_width=320&output_height=240&max_frames=10'

# GUI navigateur : configurateur de scène multi-sources en direct
uvicorn capture_helper.api:app --port 8000
# ouvrez http://localhost:8000/gui  (ou juste http://localhost:8000/)

# Docker (embarque FastAPI + GUI par défaut)
docker build -t capture-helper .
docker run --rm -p 8000:8000 capture-helper
```

La **GUI** à `/gui` est le configurateur de scène multi-sources en direct : elle énumère vos caméras et micros, prévisualise chaque caméra en direct (MJPEG) et chaque micro (vumètre), vous laisse les arranger sur un canevas, puis enregistre le tout comme un `.scene.json` réutilisable que la CLI ou l'API rejoue. Voir [📋 GUI.md](https://github.com/warith-harchaoui/capture-helper/blob/main/GUI.md).

## Auteur

 - [Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui)

## Remerciements

Remerciements chaleureux à [Mohamed Chelali](https://mchelali.github.io) et [Bachir Zerroug](https://www.linkedin.com/in/bachirzerroug) pour nos échanges fructueux.

## Licence

Ce projet est distribué sous licence BSD-3-Clause ; voir le fichier [LICENSE](https://github.com/warith-harchaoui/capture-helper/blob/main/LICENSE) pour les détails.
