# Capture Helper

[🇫🇷](https://github.com/warith-harchaoui/capture-helper/blob/main/LISEZMOI.md) · [🇬🇧](https://github.com/warith-harchaoui/capture-helper/blob/main/README.md)

[![CI](https://github.com/warith-harchaoui/capture-helper/actions/workflows/ci.yml/badge.svg)](https://github.com/warith-harchaoui/capture-helper/actions/workflows/ci.yml) [![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://github.com/warith-harchaoui/capture-helper/blob/main/LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#) [![Local-first](https://img.shields.io/badge/privacy-local--first-2f6f5e.svg)](#la-promesse)

`Capture Helper` fait partie d'une collection de bibliothèques appelée `AI Helpers`, développée pour bâtir des applications d'intelligence artificielle.

Bibliothèque local-first qui transforme une caméra ou un micro en direct en données que le reste de la suite AI Helpers sait déjà consommer, avec en plus une interface graphique dans le navigateur pour arranger plusieurs sources à la fois.

Les deux itérateurs sont toute l'idée. Chacun produit exactement ce que produit sa brique jumelle à partir d'un fichier enregistré :

| Source en direct | Itérateur | Ce qu'il produit | Identique à |
|---|---|---|---|
| Caméra | `iter_camera_frames` | un tableau par image : une grille de couleurs de pixels, hauteur × largeur × trois canaux rangés bleu, vert, rouge — le format `BGR uint8` qu'utilisent OpenCV puis le reste de la suite | `extract_frames` chez [video-helper](https://github.com/warith-harchaoui/video-helper) |
| Micro | `iter_mic_audio` | des `MicFrame` : de petits blocs de mesures audio brutes prises dans le temps, au format standard de modulation par impulsions codées (PCM) | `extract_audio_stream` chez [podcast-helper](https://github.com/warith-harchaoui/podcast-helper) |

Ce tableau est tout le bénéfice : comme les deux itérateurs parlent les formes que parlent leurs jumelles, un code écrit pour un fichier vidéo enregistré ou pour un podcast téléchargé tourne sans modification sur une caméra ou un micro en direct.

L'interface graphique se pose par-dessus. On glisse plusieurs sources en direct sur un canevas, on les prévisualise dans le navigateur, puis on enregistre la disposition comme une scène JSON réutilisable que la CLI ou l'API rejoueront plus tard. Les deux itérateurs sont le socle stable ; le configurateur de scènes, arrivé plus tard, s'appuie dessus.

[🌍 AI Helpers](https://deraison.ai/ai-helpers)

[![logo](https://raw.githubusercontent.com/warith-harchaoui/capture-helper/main/assets/logo.png)](https://deraison.ai/ai-helpers)

## La promesse

**Local-first par conception.** capture-helper s'exécute entièrement sur votre machine : les données caméra et micro sont capturées et traitées en local, jamais envoyées vers un service tiers, sans télémétrie, sans compte, sans verrouillage cloud. Fait partie de la suite [AI Helpers](https://github.com/warith-harchaoui/ai-helpers) : la souveraineté sur vos données grâce à l'open source local-first.

**Éprouvé en production, pas un prototype.** Chaque changement passe par la même porte avant publication : la suite de tests complète puis un passage de lint tournent en intégration continue (voir le badge CI ci-dessus). Seul un passage vert est tagué puis publié sur PyPI selon le versionnage sémantique.

En aval, [vocal-helper](https://github.com/warith-harchaoui/vocal-helper) s'appuie sur le flux micro en direct de capture-helper pour alimenter son pipeline vocal en production. Les itérateurs caméra puis micro encaissent donc des charges réelles, pas seulement leurs propres tests.

## Documentation

[💻 Documentation](https://deraison.ai/ai-helpers/docs/capture-helper-doc/)

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

Ce qui va au-delà d'un simple outil de prévisualisation en direct, c'est que l'agencement lui-même devient une donnée : disposer les caméras et les micros sur le canevas produit un fichier JSON portable, si bien que la même scène peut être rejouée plus tard, sur une autre machine, depuis la ligne de commande, sans navigateur.

```python
import asyncio
import capture_helper as ch

# Énumérer les périphériques disponibles
for s in ch.list_sources():
    print(f"{s['kind']:10s} [{s['index']}] {s['name']:40s} (driver={s['driver']})")
    # camera     [0] FaceTime HD Camera                       (driver=avfoundation)
    # microphone [1] MacBook Pro Microphone                   (driver=avfoundation)

# Caméra → frames numpy BGR (compatible avec video_helper.extract_frames)
cam = ch.pick_source("camera")
for frame in ch.iter_camera_frames(
    cam, output_width=640, output_height=360, fps=30, max_frames=300
):
    # frame.shape == (360, 640, 3), dtype uint8, BGR.
    do_something(frame)


# Microphone → flux PCM asynchrone (compatible avec podcast_helper.extract_audio_stream)
async def listen():
    mic = ch.pick_source("microphone")
    async for f in ch.iter_mic_audio(mic, target_sample_rate=16000, to_mono=True, frame_ms=20):
        # f["pcm"].shape == (320,), 20 ms d'audio à 16 kHz mono.
        await asr.feed(f["pcm"])


asyncio.run(listen())
```

## Comment ça marche

![Comment capture-helper fonctionne : la caméra et le micro, derrière le même contrat que le reste de la suite](https://raw.githubusercontent.com/warith-harchaoui/capture-helper/main/assets/diagrams/comment-ca-marche.png)

## Installation

**Prérequis** : **Python 3.10-3.13**, **git** et **ffmpeg**, multiplateforme :

- 🍎 **macOS** ([Homebrew](https://brew.sh)) : `brew install python git ffmpeg`
- 🐧 **Ubuntu/Debian** : `sudo apt update && sudo apt install -y python3 python3-pip git ffmpeg`
- 🪟 **Windows** (PowerShell) : `winget install Python.Python.3.12 Git.Git Gyan.FFmpeg`

Nous recommandons de travailler dans un environnement Python dédié. Si vous ne savez pas encore comment en créer un : [🥸 Astuces techniques](https://deraison.ai/4ml/#install).

`ffmpeg` doit être dans le PATH pour que l'énumération des périphériques et la capture en direct renvoient quelque chose.

### Depuis PyPI (recommandé)

```bash
# Couche INPUT de base (list/pick sources, itérateurs caméra + micro)
pip install capture-helper

# Surfaces optionnelles
pip install "capture-helper[api]"       # surface HTTP FastAPI
```

### Depuis les sources (sans PyPI)

```bash
git clone https://github.com/warith-harchaoui/capture-helper.git
cd capture-helper
pip install -e .

# Surfaces optionnelles
pip install -e ".[api]"
```

## Prise en main rapide

Le chemin utile le plus court : trouver un périphérique, lire ses images.
Aucune scène, aucun navigateur, aucune installation supplémentaire.
`list_sources` ne fait qu'appeler `ffmpeg -list_devices` : on peut donc
l'invoquer sur une machine où rien n'est branché, elle renvoie `[]` au lieu de
lever une exception.

```python
import capture_helper as ch

for s in ch.list_sources():
    print(f"{s['kind']:10s} [{s['index']}] {s['name']:40s} (driver={s['driver']})")
# camera     [0] FaceTime HD Camera                       (driver=avfoundation)
# microphone [1] MacBook Pro Microphone                   (driver=avfoundation)
# (extrait : la machine utilisée pour ce relevé liste aussi deux périphériques
#  Continuité et une entrée audio virtuelle)

cam = ch.pick_source("camera", name_substring="FaceTime")
for frame in ch.iter_camera_frames(cam, output_width=224, output_height=224, fps=30, max_frames=2):
    print(frame.shape, frame.dtype)
# (224, 224, 3) uint8
# (224, 224, 3) uint8
```

Les deux mêmes étapes depuis le terminal :

```bash
capture-helper list-sources
capture-helper capture-camera --output-dir frames/ \
    --output-width 480 --output-height 270 --fps 30 --max-frames 3
# frames/frame_000000.bgr24
# frames/frame_000001.bgr24
# frames/frame_000002.bgr24
```

**Passez `fps`.** Sur macOS, le pilote `avfoundation` se bloque au lieu
d'échouer dès que la fréquence d'images reste libre ou vaut une valeur que le
périphérique n'offre pas : un appel caméra sans `fps=` peut donc rester
suspendu indéfiniment au lieu de lever une erreur. La section
`## Dépannage` d'[EXEMPLES.md](https://github.com/warith-harchaoui/capture-helper/blob/main/EXEMPLES.md)
détaille le diagnostic, dont la façon de lister les modes acceptés par un
périphérique.

## Feuille de route

| Version | Couche | Périmètre |
|---|---|---|
| v0.0.1 | Squelette INPUT | `list_sources` + types |
| v0.1.0 | INPUT | `pick_source(...)`, `iter_camera_frames(source, ...)`, `iter_mic_audio(source, ...)` ; compose avec les contrats de video-helper et podcast-helper |
| v0.3.0 | SCÈNES + GUI | Modèle de scène (save / load / validate / resolve), primitives de prévisualisation en direct (JPEG / MJPEG caméra, niveau micro), configurateur de scène multi-sources en direct dans le navigateur à `/gui` |
| v1.0.0 | Contrats gelés | Les contrats des itérateurs cessent d'être provisoires ; la CI devient une porte bloquante plutôt qu'un rapport |
| v1.1.0 | MCP | L'app FastAPI réexposée en outils MCP (`capture-helper-mcp`, extra `[mcp]`) |
| **v1.6.0** (version actuelle) | Une porte par surface | Une seule ligne de commande `click` remplace le couple argparse / click ; les chaînes de la GUI passent à un catalogue `gettext` |
| **ensuite** | INPUT étendue | Capture d'écran ou de fenêtre ; chaîne de filtres de base (porte de bruit, gain, redimensionnement) |
| **plus tard** | PROCESS | Mixeur multi-sources : `mix_audio([sources], levels=[...])` + `compose_video([sources], layout=...)`, rejouant une scène enregistrée vers une sortie unique |

Pour un cookbook complet (chaînes d'entrée ffmpeg par système d'exploitation, capture d'instantané, prévisualisation en direct, sauvegarde et chargement de scène, câblage ASR / VAD), voir [📋 EXEMPLES.md](https://github.com/warith-harchaoui/capture-helper/blob/main/EXEMPLES.md). Pour le catalogue exhaustif de déclencheurs, voir [📋 TRIGGERS.md](https://github.com/warith-harchaoui/capture-helper/blob/main/TRIGGERS.md).

## Exposition multi-surface

`capture-helper` expose les mêmes capacités à travers **cinq surfaces**, pour se brancher là où vous travaillez déjà, sans réécriture.

| Surface | Installation | Point d'entrée | Cas d'usage |
| --- | --- | --- | --- |
| **Bibliothèque Python** | `pip install capture-helper` | `import capture_helper as ch` | Notebooks, scripts, autres AI Helpers |
| **CLI** | *(sans extra)* | `capture-helper …` | Shells, cron, CI, CMD de conteneur |
| **HTTP FastAPI** | extra `[api]` | `uvicorn capture_helper.api:app` | Service derrière un reverse-proxy, clients JSON ou multipart |
| **GUI navigateur** | extra `[api]` | `GET /gui` | Configurateur de scène multi-sources en direct (prévisualisation, arrangement, sauvegarde) |
| **MCP** | extra `[mcp]` | `capture-helper-mcp` | Tout hôte agentique compatible MCP (même app FastAPI, point d'entrée `/mcp`) |

```bash
# CLI
capture-helper list-sources
capture-helper pick-source --kind camera --name FaceTime
capture-helper capture-mic --output mic.wav --seconds 3
capture-helper stream-mic | mon-consommateur-live   # PCM f32le brut, illimité
capture-helper capture-camera --output-dir frames/ \
    --output-width 640 --output-height 360 --fps 30 --max-frames 30

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

# La même chose via Compose, port, variables et sonde de santé déjà posés
docker compose up --build
```

La **GUI** à `/gui` est le configurateur de scène multi-sources en direct : elle énumère vos caméras et micros, prévisualise chaque caméra en direct (MJPEG) et chaque micro (vumètre), vous laisse les arranger sur un canevas, puis enregistre le tout comme un `.scene.json` réutilisable que la CLI ou l'API rejoue. Voir [📋 GUI.md](https://github.com/warith-harchaoui/capture-helper/blob/main/GUI.md).

La page parle **français et anglais**. `GET /gui?lang=fr|en` choisit la langue,
un drapeau dans l'en-tête bascule de l'une à l'autre et un code que le fichier
de locales ne porte pas retombe sur la langue par défaut au lieu d'échouer.
Toutes les chaînes vivent dans
[`capture_helper/locales/fr/LC_MESSAGES/capture_helper.po`](https://github.com/warith-harchaoui/capture-helper/blob/main/capture_helper/locales/fr/LC_MESSAGES/capture_helper.po),
un catalogue `gettext` standard lu par `os_helper.Catalog` — le chargeur
partagé par la suite — si bien que
traduire la page n'oblige jamais à ouvrir un fichier Python.

### En tant que skill d'agent

`skills/capture-helper/` empaquette capture-helper comme **skill Claude** *et* skill
**OpenCode**, pour qu'un agent puisse s'en saisir à votre place. Voir
[`skills/README.md`](https://github.com/warith-harchaoui/capture-helper/blob/main/skills/README.md) pour l'installer (liens
symboliques vers `~/.claude/skills/` et `~/.opencode/skills/`) et
[`TRIGGERS.md`](https://github.com/warith-harchaoui/capture-helper/blob/main/TRIGGERS.md) pour le catalogue exhaustif des
déclencheurs — `scripts/check_triggers.py` maintient la description du skill
alignée dessus ; la suite de tests échoue si une capacité cesse d'être
nommée.

## Version Rust

Un crate compagnon, [`capture-helper-rs`](https://github.com/warith-harchaoui/capture-helper-rs), réécrit la moitié microphone en Rust natif : énumération des périphériques puis un itérateur `MicFrame` en streaming au-dessus de [`cpal`](https://crates.io/crates/cpal).

Pas de caméra, pas de GUI, pas de vidéo : uniquement le cœur de capture audio.

L'intérêt : il parle directement à CoreAudio/WASAPI/ALSA-PulseAudio-JACK-PipeWire, donc il n'a besoin ni de `ffmpeg` ni d'un runtime Python sur la machine cible. Plus adapté quand la capture micro en direct est embarquée dans une application Rust — application native, appareil embarqué — plutôt qu'orchestrée depuis Python.

## Auteur

 - [Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui)

## Remerciements

Remerciements chaleureux à [Mohamed Chelali](https://mchelali.github.io) et [Bachir Zerroug](https://www.linkedin.com/in/bachirzerroug) pour nos échanges fructueux.

## Licence

Ce projet est distribué sous licence BSD-3-Clause ; voir le fichier [LICENSE](https://github.com/warith-harchaoui/capture-helper/blob/main/LICENSE) pour les détails.
