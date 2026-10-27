# Exemples Capture Helper

[🇫🇷](https://github.com/warith-harchaoui/capture-helper/blob/main/EXEMPLES.md) · [🇬🇧](https://github.com/warith-harchaoui/capture-helper/blob/main/EXAMPLES.md)

Recettes pratiques pour `capture-helper` : **énumération et sélection de
périphériques multiplateforme, itérateurs en direct** pour caméras et
microphones, plus le modèle de scène et les primitives d'aperçu sur lesquelles
repose le configurateur navigateur.

Les sorties collées ci-dessous proviennent de l'exécution réelle des extraits
sur une machine macOS (`avfoundation`, caméra FaceTime intégrée et microphone
MacBook). Les noms de périphériques et les tailles de JPEG appartiennent à
cette machine ainsi qu'à ce que la caméra regardait ; les formes, les dtypes,
les nombres d'échantillons et les messages d'erreur, non. Quand un extrait n'a
pas pu être exécuté hors ligne — parce qu'il réclame un paquet voisin, un
modèle de parole ou un navigateur — c'est dit, plutôt que de montrer une sortie
jamais produite.

---

## Table des matières

- [Mise en place](#mise-en-place)
- [1. Lister et filtrer les sources disponibles](#1-lister-et-filtrer-les-sources-disponibles)
- [2. Choisir un périphérique précis](#2-choisir-un-périphérique-précis)
- [3. Caméra → frames numpy BGR](#3-caméra--frames-numpy-bgr)
- [4. Microphone → flux PCM asynchrone](#4-microphone--flux-pcm-asynchrone)
- [5. Composer avec les contrats video-helper / podcast-helper](#5-composer-avec-les-contrats-video-helper--podcast-helper)
- [6. Construire soi-même la chaîne d'entrée ffmpeg par OS](#6-construire-soi-même-la-chaîne-dentrée-ffmpeg-par-os)
- [7. Inspecter un dictionnaire typé `Source`](#7-inspecter-un-dictionnaire-typé-source)
- [8. Concevoir, enregistrer et rejouer une scène](#8-concevoir-enregistrer-et-rejouer-une-scène)
- [9. Aperçu en direct (JPEG / MJPEG / niveau micro)](#9-aperçu-en-direct-jpeg--mjpeg--niveau-micro)
- [10. Le configurateur de scène dans le navigateur (`/gui`)](#10-le-configurateur-de-scène-dans-le-navigateur-gui)
- [Ligne de commande](#ligne-de-commande)
- [Dépannage](#dépannage)

---

## Mise en place

```bash
pip install capture-helper
pip install "capture-helper[api]"   # seulement pour les sections 9-10 (HTTP + GUI)
```

`ffmpeg` doit être dans le `PATH` : c'est le moteur de capture, pas un
accélérateur optionnel. `brew install ffmpeg` sur macOS (après avoir installé
`brew` depuis [brew.sh](https://brew.sh/)), `sudo apt install ffmpeg` sur
Linux ; sous Windows, un build ajouté au `PATH`. Aucun PortAudio ici : le chemin
audio passe aussi par ffmpeg.

Chaque extrait ci-dessous suppose ces imports :

```python
import asyncio

import capture_helper as ch
```

## 1. Lister et filtrer les sources disponibles

`list_sources` appelle `ffmpeg -list_devices` en sous-main et parse sa sortie
stderr. Si `ffmpeg` manque — ou si la plateforme n'est pas encore routée — elle
renvoie `[]` au lieu de lever une exception, ce qui en fait une sonde « cette
machine est-elle prête à capturer ? ».

```python
for s in ch.list_sources():
    print(f"{s['kind']:10s} [{s['index']}] {s['name']:40s} (driver={s['driver']})")
# camera     [0] FaceTime HD Camera                       (driver=avfoundation)
# microphone [1] MacBook Pro Microphone                   (driver=avfoundation)
# (extrait : la machine liste aussi deux périphériques Continuité et une
#  entrée audio virtuelle)
```

Passez un type pour n'obtenir qu'une moitié du catalogue :

```python
print(
    len(ch.list_sources("camera")),
    "camera(s),",
    len(ch.list_sources("microphone")),
    "microphone(s)",
)
# 3 camera(s), 3 microphone(s)
```

`darwin`, `linux` et `windows` sont routés aujourd'hui. Partout ailleurs le
catalogue revient vide — là encore sans exception.

## 2. Choisir un périphérique précis

`pick_source` renvoie le **premier** périphérique satisfaisant toutes les
contraintes données, dans l'ordre de la liste OS ; elle lève `ValueError`
quand aucun ne convient.

```python
cam = ch.pick_source("camera")
print(cam["name"])
# FaceTime HD Camera

# Sous-chaîne de nom insensible à la casse : la façon stable de sélectionner
# d'une machine à l'autre, où l'ordre de la liste OS varie.
mic = ch.pick_source("microphone", name_substring="macbook")
print(mic["name"])
# MacBook Pro Microphone

# Index exact dans la liste OS.
print(ch.pick_source("camera", index=0))
# {'kind': 'camera', 'name': 'FaceTime HD Camera', 'index': 0,
#  'platform': 'darwin', 'driver': 'avfoundation'}
```

Quand rien ne correspond, le message dit exactement ce qui a été tenté et
combien de candidats il avait sous la main :

```python
ch.pick_source("microphone", name_substring="USB")
# ValueError: No microphone matches constraints (name_substring='USB', index=None).
# Catalog had 3 candidate(s); call list_sources('microphone') to inspect.
```

## 3. Caméra → frames numpy BGR

`iter_camera_frames` produit des tableaux numpy uint8 BGR de forme `(H, W, 3)` :
**la même forme et le même dtype que
[`video_helper.extract_frames`](https://github.com/warith-harchaoui/video-helper)**.
Les consommateurs écrits pour le chemin fichier s'y branchent sans rien
changer.

```python
cam = ch.pick_source("camera")

# 224x224 en letterbox (ratio préservé, padding noir) : forme d'entrée ML courante.
for frame in ch.iter_camera_frames(cam, output_width=224, output_height=224, fps=30, max_frames=2):
    print(frame.shape, frame.dtype)
# (224, 224, 3) uint8
# (224, 224, 3) uint8
```

**Passez toujours `fps`.** Sur macOS, le pilote `avfoundation` se bloque au
lieu d'échouer dès que la fréquence d'images reste libre ou vaut une valeur que
le périphérique n'offre pas : un appel sans `fps=` peut rester suspendu
indéfiniment. Le [Dépannage](#dépannage) explique comment lister les modes
qu'un périphérique accepte.

Au moins une paire de résolution est obligatoire, car le tuyau `bgr24` brut ne
porte aucun en-tête : le lecteur doit connaître la taille d'image à l'avance.

```python
next(iter(ch.iter_camera_frames(cam)))
# ValueError: iter_camera_frames requires (width, height) and/or
# (output_width, output_height) so the raw byte stream can be reshaped.
# Set at least one pair, or query the device's modes ahead of time.
```

Fixez `width` / `height` côté capture et `output_width` / `output_height` côté
post-décodage ; fixez les deux pour un contrôle complet. Une fenêtre en direct
demande OpenCV, dont `capture-helper` ne dépend pas — installez-le vous-même et
les frames y entrent telles quelles, sans conversion :

```python
import cv2  # pas une dépendance de capture-helper

for frame in ch.iter_camera_frames(cam, width=1280, height=720, fps=30):
    cv2.imshow("preview", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break
cv2.destroyAllWindows()
```

*(Non exécuté ici : il faut un affichage.)*

## 4. Microphone → flux PCM asynchrone

`iter_mic_audio` produit des dictionnaires typés `MicFrame` : **la même forme
que
[`podcast_helper.extract_audio_stream`](https://github.com/warith-harchaoui/podcast-helper)**.
Le PCM est en float32 dans `[-1.0, 1.0]`, rééchantillonné vers
`target_sample_rate` par libswresample de ffmpeg (passe-bas anti-repliement au
nouveau Nyquist).

```python
async def listen():
    mic = ch.pick_source("microphone", name_substring="macbook")
    async for f in ch.iter_mic_audio(
        mic, target_sample_rate=16000, to_mono=True, frame_ms=20, max_frames=4
    ):
        print(f["pcm"].shape, f["pcm"].dtype, round(f["t_abs_s"], 3), f["voiced"])


asyncio.run(listen())
# (320,) float32 0.0 None
# (320,) float32 0.02 None
# (320,) float32 0.04 None
# (320,) float32 0.06 None
```

320 échantillons, c'est 20 ms à 16 kHz mono. `t_abs_s` est monotone depuis
l'instant où ffmpeg s'est accroché au périphérique ; `voiced` reste `None` ici
— c'est un VAD en aval qui le renseigne.

Retirez `max_frames` pour un flux illimité ; calculez-le pour une capture
bornée :

```python
async def record_5s():
    mic = ch.pick_source("microphone", name_substring="macbook")
    return [f["pcm"] async for f in ch.iter_mic_audio(mic, max_frames=5 * 50)]


chunks = asyncio.run(record_5s())
print(len(chunks))
# 250
```

Contrairement à la caméra, le chemin microphone n'a besoin d'aucune indication
de cadence : `frame_ms` fixe déjà la taille des blocs.

## 5. Composer avec les contrats video-helper / podcast-helper

Tout l'intérêt des deux itérateurs : **une caméra ou un micro en direct se
branche sur n'importe quel pipeline écrit pour les helpers sur fichier, sans
code de liaison**.

```python
import numpy as np

import podcast_helper as ph


# La même boucle VAD / ASR tourne sur :
#   - un flux de podcast (ph.extract_audio_stream)
#   - un fichier local   (même appel)
#   - un micro en direct (ch.iter_mic_audio)
async def transcribe(frames_async_iter):
    chunks = []
    async for f in frames_async_iter:
        chunks.append(f["pcm"])
        if len(chunks) * 0.02 >= 5.0:  # toutes les 5 secondes
            audio = np.concatenate(chunks)
            print(whisper.transcribe(audio))
            chunks.clear()


# Piloté par le flux
asyncio.run(transcribe(ph.extract_audio_stream("https://feeds.npr.org/510289/podcast.xml")))

# Piloté par le micro : code en aval identique
mic = ch.pick_source("microphone")
asyncio.run(transcribe(ch.iter_mic_audio(mic, target_sample_rate=16000)))
```

*(Non exécuté ici : il faut `podcast-helper`, un accès réseau et un modèle de
parole. Les deux appels capture-helper sont vérifiés face au code ; `whisper`
tient la place de l'ASR de votre choix.)*

La même composabilité vaut côté vidéo. `video_helper.iter_frame_optical_flow`
enveloppe n'importe quel itérateur de frames `(H, W, 3)` BGR uint8 sans se
soucier de savoir si elles viennent d'un fichier
(`video_helper.extract_frames`) ou d'une caméra en direct
(`ch.iter_camera_frames`) : les deux partagent déjà exactement ce contrat. Flux
optique dense en direct, sans code de liaison ni nouvelle dépendance de ce
côté-ci — capture-helper reste ffmpeg + numpy, le poids OpenCV / Torch restant
entièrement chez video-helper.

```python
import video_helper as vh

cam = ch.pick_source("camera")
frames = ch.iter_camera_frames(cam, width=1280, height=720, fps=30)

# Même appel que vh.iter_frame_optical_flow(vh.extract_frames("clip.mp4"), method="dis").
# Seule la source de frames a changé, d'un fichier vers une caméra en direct.
for flow_frame in vh.iter_frame_optical_flow(frames, method="dis"):
    bgr = flow_frame[..., :3].astype("uint8")  # retour à une frame classique
    vx, vy = flow_frame[..., 3], flow_frame[..., 4]  # mouvement par pixel en direct
```

*(Non exécuté ici : il faut `video-helper` installé. `iter_frame_optical_flow`
produit du `(H, W, 5)` float32 — BGR plus `vx` / `vy` — ce que découpent les
trois tranches ci-dessus.)*

## 6. Construire soi-même la chaîne d'entrée ffmpeg par OS

Pour qui câble son propre pipeline ffmpeg, le constructeur d'argv par OS est
public :

```python
cam = ch.pick_source("camera")
print(ch.ffmpeg_input_args(cam))
# ['-f', 'avfoundation', '-i', '0:none']

mic = ch.pick_source("microphone", name_substring="macbook")
print(ch.ffmpeg_input_args(mic))
# ['-f', 'avfoundation', '-i', 'none:1']
```

`avfoundation` adresse les périphériques en `"<vidéo>:<audio>"`, où `none`
renonce à la piste qu'on ne capture pas : d'où `0:none` pour la caméra et
`none:1` pour le microphone. Insérez le fragment dans une commande à vous :

```python
import subprocess

cmd = [
    "ffmpeg",
    "-hide_banner",
    "-loglevel",
    "error",
    "-framerate",
    "30",  # avfoundation se bloque sans cela
    *ch.ffmpeg_input_args(cam),
    "-frames:v",
    "1",
    "-update",
    "1",
    "-y",
    "snapshot.png",
]
subprocess.run(cmd, check=True)
print("wrote snapshot.png from", cam["name"])
# wrote snapshot.png from FaceTime HD Camera
```

`avfoundation` crache au passage une liste de formats de pixels sur stderr,
même en `-loglevel error`. C'est du bavardage, pas un échec : le code de sortie
vaut 0 et le fichier est bien écrit.

`ffmpeg_input_args` lève `ValueError` sur un driver qu'elle ne connaît pas : une
vérification de bon sens peu coûteuse avant de lancer quoi que ce soit.

## 7. Inspecter un dictionnaire typé `Source`

```python
from capture_helper import Source  # importable pour le typage en aval

sources: list[Source] = ch.list_sources("camera")
print(sources[0])
# {'kind': 'camera', 'name': 'FaceTime HD Camera', 'index': 0,
#  'platform': 'darwin', 'driver': 'avfoundation'}
```

Le schéma : `kind` ∈ `{"camera", "microphone"}`, `driver` ∈ `{"avfoundation",
"v4l2", "dshow", "pulse", "alsa"}`, `platform` ∈ `{"darwin", "linux",
"windows"}`. Le champ `driver` est aussi le drapeau de format d'entrée ffmpeg
que le code en aval utilisera : `-f avfoundation`, `-f v4l2`, `-f dshow`,
`-f pulse`, `-f alsa`.

## 8. Concevoir, enregistrer et rejouer une scène

Une **scène** est un artefact JSON réutilisable décrivant une composition
multi-sources : un canevas nommé plus des caméras et des microphones placés
avec leurs paramètres de capture. On en construit une en code, on
l'enregistre, on la rejoue plus tard ou sur une autre machine.

```python
scene = ch.new_scene("studio", width=1280, height=720)
scene = ch.add_source(
    scene, kind="camera", name_substring="FaceTime", x=0, y=0, w=1280, h=720, params={"fps": 30}
)
scene = ch.add_source(scene, kind="microphone", name_substring="MacBook")

print([s["label"] for s in scene["sources"]])
# ['camera 1', 'microphone 1']
```

`add_source` ne mute jamais son entrée — elle renvoie une nouvelle scène — et
étiquette chaque tuile `"<kind> <n>"` à moins de passer `label=` soi-même.

```python
print(ch.save_scene(scene, "studio.scene.json"))
# /chemin/absolu/vers/studio.scene.json

# Plus tard : la recharger et voir comment chaque source se résout sur CETTE machine.
scene = ch.load_scene("studio.scene.json")
for r in ch.resolve_scene_sources(scene):
    label = r["scene_source"]["label"]
    print(label, "->", (r["resolved"]["name"] if r["resolved"] else r["error"]))
# camera 1 -> FaceTime HD Camera
# microphone 1 -> MacBook Pro Microphone
```

`save_scene` valide à l'écriture et renvoie le chemin absolu écrit ;
`load_scene` valide à la lecture. Une source qui ne se résout pas ici n'est pas
une erreur : `resolved` vaut `None` et `error` porte la raison, si bien qu'un
périphérique débranché ne coule pas la scène entière.

On peut aussi laisser la machine amorcer une scène de départ avec ce qu'elle a.
L'étiquette y est le nom complet du périphérique plutôt qu'un nom généré :

```python
scene = ch.scene_from_available_devices("auto")
print(scene["name"], scene["width"], scene["height"], len(scene["sources"]))
# auto 1280 720 2
```

## 9. Aperçu en direct (JPEG / MJPEG / niveau micro)

Ces primitives alimentent la GUI navigateur ; elles s'appellent aussi
directement.

```python
cam = ch.pick_source("camera")

# Un flux de JPEG : exactement ce que concatène l'endpoint MJPEG.
for i, jpg in enumerate(ch.iter_camera_jpeg(cam, fps=30, max_frames=2)):
    print(i, len(jpg), "bytes")
# 0 3895 bytes
# 1 3895 bytes
```

La taille dépend de ce que la caméra regarde — l'auto-exposition seule la fait
bouger entre deux exécutions à une minute d'intervalle — donc la vôtre
différera. `fps` compte pour la même raison qu'à la section 3. Pour une seule image, bornez le
flux à un :

```python
jpg = next(iter(ch.iter_camera_jpeg(cam, fps=30, max_frames=1)))
print(len(jpg), "bytes", jpg[:3])
# 9475 bytes b'\xff\xd8\xff'
```

`snapshot_jpeg(cam)` est l'écriture courte de ce qui précède, mais elle
n'accepte aucun argument `fps` et ne peut donc en transmettre aucun à la
caméra : sur un périphérique `avfoundation` qui réclame une cadence explicite,
elle se bloque. Préférez les deux lignes ci-dessus tant que ce n'est pas
corrigé.

`frame_to_jpeg` encode un tableau que vous tenez déjà : elle ne touche aucun
périphérique.

```python
import numpy as np

frame = np.zeros((48, 64, 3), dtype=np.uint8)
frame[:, :, 2] = 255  # rouge pur, en ordre de canaux BGR
print(len(ch.frame_to_jpeg(frame)), "bytes")
# 242 bytes
```

Niveau microphone, pour un vumètre :

```python
mic = ch.pick_source("microphone", name_substring="MacBook")
print(asyncio.run(ch.mic_level(mic)))
# {'rms': 0.0017772795343478113, 'rms_dbfs': -55.00488520104408,
#  'peak': 0.005553045775741339, 'peak_dbfs': -45.10937492936038}
```

Ce relevé est celui d'une pièce calme. `mic_level` capture environ `window_ms`
d'audio (200 ms par défaut) et rapporte du silence plutôt que de lever une
exception quand elle n'obtient rien : une GUI qui l'interroge toutes les
quelques centaines de millisecondes n'a donc jamais à attraper d'erreur.

Par HTTP, avec l'extra `[api]` :

```bash
uvicorn capture_helper.api:app --port 8000
curl http://localhost:8000/health                            # {"status":"ok"}
curl http://localhost:8000/sources
curl 'http://localhost:8000/input-args?kind=microphone&index=1'
# {"argv":["-f","avfoundation","-i","none:1"]}
curl -o thumb.jpg 'http://localhost:8000/preview/camera.jpg?output_width=480'
curl 'http://localhost:8000/preview/mic-level'
# Flux MJPEG : <img src="http://localhost:8000/preview/camera.mjpeg">
```

*(Les deux réponses montrées ont été obtenues sur la même application via le
`TestClient` de FastAPI plutôt que sur un port à l'écoute.)*

## 10. Le configurateur de scène dans le navigateur (`/gui`)

```bash
pip install 'capture-helper[api]'
uvicorn capture_helper.api:app --port 8000
# ouvrez http://localhost:8000/gui  (ou simplement http://localhost:8000/)
```

Énumérez vos caméras et vos micros, cliquez pour les déposer sur le canevas,
prévisualisez chaque caméra en direct (MJPEG) et chaque micro (vumètre),
glissez pour les arranger, puis **Save scene (JSON)** : le `.scene.json`
téléchargé est exactement ce que consomment `capture-helper scene-validate`,
`scene-show` et `ch.load_scene(...)`. `GET /gui?lang=fr` sert la même page en
français. Voir
[GUI.md](https://github.com/warith-harchaoui/capture-helper/blob/main/GUI.md)
pour le mode d'emploi complet. Tout est local : aucun envoi, aucune
télémétrie.

## Ligne de commande

Une seule ligne de commande, bâtie avec `click`, neuf sous-commandes. Les noms
de drapeaux reprennent les arguments nommés de la bibliothèque.

```bash
capture-helper --help
# Commands:
#   capture-camera  Capture N frames from a camera and write raw bgr24...
#   capture-mic     Record N seconds of microphone audio to a WAV file.
#   input-args      Print the ffmpeg ``-f DRIVER -i SPEC`` argv fragment...
#   list-sources    Enumerate available capture devices (JSON output).
#   pick-source     Pick a single capture device by kind / name / index...
#   scene-auto      Emit a scene auto-populated from this host's cameras /...
#   scene-show      Load a scene and report how each source resolves on...
#   scene-validate  Validate a scene JSON file (exit 0 when well-formed).
#   stream-mic      Stream live microphone PCM (raw f32le) to stdout,...
```

Lectures — le catalogue de périphériques et le fragment ffmpeg :

```bash
capture-helper list-sources --kind camera
capture-helper pick-source --kind camera --name FaceTime
# {
#   "kind": "camera",
#   "name": "FaceTime HD Camera",
#   "index": 0,
#   "platform": "darwin",
#   "driver": "avfoundation"
# }
capture-helper input-args --kind microphone --index 1
# -f avfoundation -i none:1
```

Captures — des frames dans un dossier, de l'audio dans un WAV, de l'audio dans
un tuyau :

```bash
capture-helper capture-camera --output-dir frames/ \
    --output-width 480 --output-height 270 --fps 30 --max-frames 3
# frames/frame_000000.bgr24
# frames/frame_000001.bgr24
# frames/frame_000002.bgr24

capture-helper capture-mic --output mic.wav --seconds 2 --name MacBook
# mic.wav

capture-helper stream-mic --name MacBook --seconds 1 | wc -c
# 64000
```

Chaque fichier `.bgr24` pèse `largeur × hauteur × 3` octets — 388800 pour
480×270 — sans en-tête, exactement ce que produit `iter_camera_frames`.
`stream-mic` écrit du `f32le` brut : une seconde à 16 kHz mono par défaut fait
donc 64000 octets. Omettez `--seconds` et la commande tourne jusqu'à ce que le
consommateur s'en aille.

Scènes — en amorcer une depuis l'hôte, la contrôler, voir comment elle se
résout ici :

```bash
capture-helper scene-auto --name studio --output studio.scene.json
capture-helper scene-validate --input studio.scene.json
# ok: studio.scene.json is a valid scene (2 source(s))
capture-helper scene-show --input studio.scene.json
```

Une exception de la bibliothèque revient en une ligne sur stderr plus un code
de sortie 1, pas en traceback :

```bash
capture-helper pick-source --kind microphone --name USB
# Error: No microphone matches constraints (name_substring='USB', index=None).
# Catalog had 3 candidate(s); call list_sources('microphone') to inspect.
```

## Dépannage

**Un appel caméra se bloque sans jamais produire d'image.** Sur macOS, c'est
presque toujours la cadence. `avfoundation` n'accepte que les modes annoncés
par le périphérique ; une demande inacceptable fait attendre ffmpeg au lieu de
le faire sortir — relevé sur une caméra FaceTime HD qui annonce 15 et 30
fps : `fps=30` fonctionne, tandis que laisser `fps` libre, `fps=10` et même
`fps=15` ne produisent rien jusqu'à ce qu'on tue le processus. Demandez à
ffmpeg un mode impossible puis lisez la liste qu'il renvoie :

```bash
ffmpeg -hide_banner -framerate 1 -f avfoundation -i "0:none" -frames:v 1 -f null -
# Supported modes:
#   1552x1552@[15.000000 30.000000]fps
#   ...
# Error opening input: Input/output error
```

Passez ensuite l'un de ces nombres en `fps=` ou `--fps`.

**`list_sources()` renvoie une liste vide.** Soit `ffmpeg` n'est pas dans le
`PATH`, soit la plateforme n'est pas routée (seuls `darwin`, `linux` et
`windows` le sont). `list_sources` est volontairement « au mieux » et ne lève
jamais : un catalogue vide est donc le seul signal disponible. Vérifiez
`shutil.which("ffmpeg")` d'abord.

**`RuntimeError: ffmpeg exited before yielding a frame`.** Le périphérique s'est
ouvert mais n'a rien produit : permission refusée par le système, caméra tenue
par une autre application. Sur macOS, accordez l'accès Caméra et
Microphone au programme qui *exécute* Python — Terminal, iTerm, votre IDE —
dans Réglages Système → Confidentialité et sécurité : la demande va à
l'application hôte, pas à Python. Sur Linux, vérifiez que votre utilisateur est
dans le groupe `video` pour `/dev/video*`.

**`ValueError: iter_camera_frames requires (width, height) and/or
(output_width, output_height)`.** Du `bgr24` brut sorti d'un tuyau ne porte
aucun en-tête : la taille d'image doit être connue avant la première lecture.
Fixez une paire côté capture, une paire côté sortie, les deux au besoin.

**`ValueError: quality must be between 2 (best) and 31 (worst)`.** Le réglage
JPEG de `frame_to_jpeg`, `snapshot_jpeg` et `iter_camera_jpeg` est l'échelle
`-q:v` de ffmpeg, qui va dans le sens *inverse* de l'échelle 0-100 d'OpenCV et
de Pillow. `quality=90` est rejeté exprès plutôt que silencieusement ramené
dans les bornes.

**Fichiers de scène.** Un fichier absent lève `FileNotFoundError: scene file
not found: <chemin>` ; un fichier malformé lève un `ValueError` qui nomme le
champ — `scene width must be a positive int, got 0`, par exemple. Les deux
sortent de la validation : une scène qui se charge est donc une scène que le
reste de l'API acceptera.
