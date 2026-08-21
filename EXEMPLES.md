# Exemples Capture Helper

Recettes pratiques pour `capture-helper` v0.1.0 : **énumération et sélection
de périphériques multiplateforme, plus itérateurs live** pour caméras et
microphones.

Chaque extrait suppose :

```python
import asyncio
import capture_helper as ch
```

et que `ffmpeg` est dans le PATH (`brew install ffmpeg` sur macOS, en
installant `brew` grâce à [brew.sh](https://brew.sh/) ; `sudo apt install
ffmpeg` sur Linux ; un build Windows ajouté au `PATH`).

---

## Sommaire

1. [Mise en place](#mise-en-place)
2. [Lister toutes les sources disponibles](#lister-toutes-les-sources-disponibles)
3. [Filtrer par type (caméra / microphone)](#filtrer-par-type-caméra--microphone)
4. [Choisir un périphérique précis](#choisir-un-périphérique-précis)
5. [Caméra → frames numpy BGR](#caméra--frames-numpy-bgr)
6. [Microphone → flux PCM async](#microphone--flux-pcm-async)
7. [Composer avec les contrats video-helper / podcast-helper](#composer-avec-les-contrats-video-helper--podcast-helper)
8. [Construire soi-même la chaîne d'entrée ffmpeg par OS](#construire-soi-même-la-chaîne-dentrée-ffmpeg-par-os)
9. [Inspecter un dictionnaire typé `Source`](#inspecter-un-dictionnaire-typé-source)
10. [Concevoir, enregistrer et rejouer une scène](#concevoir-enregistrer-et-rejouer-une-scène)
11. [Aperçu live (JPEG / MJPEG / niveau micro)](#aperçu-live-jpeg--mjpeg--niveau-micro)
12. [Le configurateur de scène navigateur (`/gui`)](#le-configurateur-de-scène-navigateur-gui)
13. [Feuille de route : ce que chaque version débloque](#feuille-de-route--ce-que-chaque-version-débloque)

---

## Mise en place

```bash
pip install --force-reinstall --no-cache-dir \
    capture-helper
```

L'appel `list_sources` invoque `ffmpeg -list_devices` et parse sa sortie
stderr. Si `ffmpeg` est absent, l'appel renvoie `[]` plutôt que de lever une
exception : pratique pour une sonde « cette machine est-elle prête à
capturer ? ».

## Lister toutes les sources disponibles

```python
for s in ch.list_sources():
    print(f"{s['kind']:10s} [{s['index']}] {s['name']:40s} (driver={s['driver']})")
    # camera     [0] FaceTime HD Camera                       (driver=avfoundation)
    # camera     [1] iPhone Camera                            (driver=avfoundation)
    # microphone [0] Built-in Microphone                      (driver=avfoundation)
    # microphone [1] BlackHole 16ch                           (driver=avfoundation)
```

(Sortie typique sur macOS avec avfoundation.)

## Filtrer par type (caméra / microphone)

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

`list_sources` renvoie `[]` sur les plateformes pas encore couvertes
(darwin / linux / windows sont pris en charge actuellement) ; elle ne lève
jamais d'exception.

## Choisir un périphérique précis

`pick_source` renvoie le premier périphérique qui correspond aux
contraintes ; à défaut, elle lève `ValueError`.

```python
# Première caméra disponible.
cam = ch.pick_source("camera")
print(cam["name"])
# FaceTime HD Camera

# Choisir par sous-chaîne de nom insensible à la casse (pratique pour une
# sélection stable d'une machine à l'autre, où l'ordre de la liste OS varie).
mic = ch.pick_source("microphone", name_substring="blackhole")
print(mic["name"])
# BlackHole 16ch

# Choisir par index exact dans la liste OS.
usb_cam = ch.pick_source("camera", index=1)
print(usb_cam["name"])
# iPhone Camera
```

Quand rien ne correspond, le message d'erreur dit exactement ce qui a été
tenté :

```python
ch.pick_source("microphone", name_substring="USB")
# ValueError: No microphone matches constraints
# (name_substring='USB', index=None).
# Catalog had 2 candidate(s); call list_sources('microphone') to inspect.
```

## Caméra → frames numpy BGR

`iter_camera_frames` produit des tableaux numpy uint8 BGR de forme `(H, W,
3)`, **la même forme et le même dtype que
[`video_helper.extract_frames`](https://github.com/warith-harchaoui/video-helper)**.
Les consommateurs conçus pour le chemin basé fichier s'y branchent sans
aucune modification.

```python
import cv2

cam = ch.pick_source("camera")

# Aperçu live, 720p à 30 fps, jusqu'à ce que l'utilisateur appuie sur 'q'.
for frame in ch.iter_camera_frames(cam, width=1280, height=720, fps=30):
    cv2.imshow("preview", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break
cv2.destroyAllWindows()

# 224x224 en letterbox (ratio préservé, padding noir) : forme d'entrée ML courante.
for frame in ch.iter_camera_frames(cam, output_width=224, output_height=224,
                                   max_frames=10):
    # frame.shape == (224, 224, 3), dtype uint8, BGR.
    print(frame.shape, frame.dtype)
    # (224, 224, 3) uint8
```

`iter_camera_frames` exige au moins une des deux paires de résolution
(``(width, height)`` côté capture ou ``(output_width, output_height)`` côté
post-décodage) pour pouvoir remettre en forme le flux d'octets brut ; fixez
les deux pour un contrôle complet.

## Microphone → flux PCM async

`iter_mic_audio` produit des dictionnaires typés `MicFrame`, **la même forme
que
[`podcast_helper.extract_audio_stream`](https://github.com/warith-harchaoui/podcast-helper)**.
Le PCM est en float32 dans `[-1.0, 1.0]`, rééchantillonné vers
`target_sample_rate` via libswresample de ffmpeg (passe-bas anti-repliement
au nouveau Nyquist).

```python
async def listen():
    mic = ch.pick_source("microphone")
    async for f in ch.iter_mic_audio(mic,
                                     target_sample_rate=16000,
                                     to_mono=True,
                                     frame_ms=20):
        # f["pcm"].shape == (320,) pour 20 ms à 16 kHz mono.
        # f["t_abs_s"] est monotone depuis l'instant où ffmpeg s'est accroché.
        # f["voiced"] vaut None : un VAD en aval le renseigne s'il est utilisé.
        print(f["pcm"].shape, f["t_abs_s"])
        # (320,) 0.0
        # (320,) 0.02
        # (320,) 0.04
        # ...

asyncio.run(listen())
```

Passez `max_frames=N` pour une capture bornée :

```python
async def record_5s():
    mic = ch.pick_source("microphone")
    chunks = []
    async for f in ch.iter_mic_audio(mic, max_frames=5 * 50):  # 50 frames/s à 20 ms
        chunks.append(f["pcm"])
    return chunks

audio_chunks = asyncio.run(record_5s())
print(len(audio_chunks))
# 250
```

## Composer avec les contrats video-helper / podcast-helper

Tout l'intérêt de la v0.1.0 : **une caméra ou un micro live se branche sur
n'importe quel pipeline conçu pour les helpers basés fichier, sans code de
liaison**.

```python
import asyncio
import capture_helper as ch
import podcast_helper as ph

# La même boucle VAD / ASR fonctionne sur :
#   - une URL YouTube (via ph.extract_audio_stream)
#   - un fichier local (idem)
#   - un micro live (via ch.iter_mic_audio)
async def transcribe(frames_async_iter):
    chunks = []
    async for f in frames_async_iter:
        chunks.append(f["pcm"])
        if len(chunks) * 0.02 >= 5.0:           # toutes les 5 secondes
            audio = np.concatenate(chunks)
            print(whisper.transcribe(audio))
            # "And in tonight's headlines, the Senate voted..."
            chunks.clear()

# Piloté par URL
asyncio.run(transcribe(ph.extract_audio_stream("https://feeds.npr.org/510289/podcast.xml")))

# Piloté par le micro : même code en aval
mic = ch.pick_source("microphone")
asyncio.run(transcribe(ch.iter_mic_audio(mic, target_sample_rate=16000)))
```

La même composabilité fonctionne côté vidéo. `video_helper.iter_frame_optical_flow`
accepte n'importe quel itérateur de frames `(H, W, 3)` BGR uint8 : peu importe
que les frames viennent d'un fichier (`video_helper.extract_frames`) ou d'une
caméra live (`ch.iter_camera_frames`), puisque les deux partagent exactement
le même contrat. Flux optique dense en direct, sans code de liaison, sans
nouvelle dépendance côté capture-helper (qui reste ffmpeg + numpy uniquement ;
c'est `video_helper[flow]` qui apporte opencv/torch, entièrement côté
video-helper) :

```python
import capture_helper as ch
import video_helper as vh

cam = ch.pick_source("camera")
frames = ch.iter_camera_frames(cam, width=1280, height=720, fps=30)

# Même appel que vh.iter_frame_optical_flow(vh.extract_frames("clip.mp4"), method="dis").
# Seule la source de frames a changé, d'un fichier vers une caméra live.
for flow_frame in vh.iter_frame_optical_flow(frames, method="dis"):
    bgr = flow_frame[..., :3].astype("uint8")        # retour à une frame classique
    vx, vy = flow_frame[..., 3], flow_frame[..., 4]  # mouvement par pixel en direct
```

## Construire soi-même la chaîne d'entrée ffmpeg par OS

Pour les utilisateurs qui câblent leur propre pipeline ffmpeg, le
constructeur d'argv par OS est exposé :

```python
import shlex, subprocess

cam = ch.pick_source("camera")
input_args = ch.ffmpeg_input_args(cam)
# ['-f', 'avfoundation', '-i', '0:none']

# Capture ponctuelle.
cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error",
       *input_args,
       "-frames:v", "1", "snapshot.png"]
subprocess.run(cmd, check=True)
print("Saved snapshot.png from", cam["name"])
# Saved snapshot.png from FaceTime HD Camera
```

`ffmpeg_input_args` lève `ValueError` pour un driver inconnu : une
vérification de bon sens utile avant de lancer ffmpeg.

## Inspecter un dictionnaire typé `Source`

```python
from capture_helper import Source, SourceKind  # importable pour le typage en aval

sources: list[Source] = ch.list_sources()
for s in sources:
    print(s)
    # {'kind': 'camera', 'name': 'FaceTime HD Camera', 'index': 0,
    #  'platform': 'darwin', 'driver': 'avfoundation'}
    # (schéma : kind ∈ {"camera", "microphone"} ; driver ∈ {"avfoundation",
    #  "v4l2", "dshow", "pulse", "alsa"} ; platform ∈ {"darwin", "linux",
    #  "windows"}.)
```

Le champ `driver` indique le drapeau de format d'entrée ffmpeg que le code
en aval utilisera : `-f avfoundation`, `-f v4l2`, `-f dshow`, `-f pulse` ou
`-f alsa`.

## Concevoir, enregistrer et rejouer une scène

Une **scène** est un artefact JSON réutilisable qui décrit une composition
multi-sources : un canevas nommé plus des caméras / microphones placés avec
leurs paramètres de capture. Vous pouvez en construire une en code,
l'enregistrer, puis la rejouer plus tard (ou sur une autre machine).

```python
import capture_helper as ch

# Construire une scène : une caméra plein canevas + un microphone.
scene = ch.new_scene("studio", width=1280, height=720)
scene = ch.add_source(scene, kind="camera", name_substring="FaceTime",
                      x=0, y=0, w=1280, h=720, params={"fps": 30})
scene = ch.add_source(scene, kind="microphone", name_substring="Built-in")

# La persister (validée à l'écriture).
ch.save_scene(scene, "studio.scene.json")

# Plus tard : la recharger et voir comment chaque source se résout sur CETTE machine.
scene = ch.load_scene("studio.scene.json")
for r in ch.resolve_scene_sources(scene):
    src = r["scene_source"]
    print(src["label"], "->", (r["resolved"]["name"] if r["resolved"] else r["error"]))
    # host cam -> FaceTime HD Camera
    # microphone 1 -> Built-in Microphone
```

Ou laisser la machine amorcer une scène de départ à partir de ce qu'elle a :

```python
scene = ch.scene_from_available_devices("auto")   # première caméra + premier micro
ch.save_scene(scene, "auto.scene.json")
```

Depuis le terminal (les deux CLI partagent les mêmes sous-commandes) :

```bash
capture-helper scene-auto --name studio --output studio.scene.json
capture-helper scene-validate --input studio.scene.json     # code 0 si valide
capture-helper scene-show     --input studio.scene.json     # rapport de résolution JSON
```

## Aperçu live (JPEG / MJPEG / niveau micro)

Les primitives d'aperçu alimentent la GUI navigateur, mais vous pouvez les
appeler directement.

```python
import asyncio
import capture_helper as ch

cam = ch.pick_source("camera")

# Une frame live en octets JPEG (par ex. pour écrire une vignette).
jpg = ch.snapshot_jpeg(cam, output_width=480, output_height=270)
with open("thumb.jpg", "wb") as f:
    f.write(jpg)

# Un flux de JPEG (ce que concatène l'endpoint MJPEG).
for i, frame_jpg in enumerate(ch.iter_camera_jpeg(cam, fps=10, max_frames=5)):
    print(i, len(frame_jpg), "bytes")

# Niveau microphone pour un vumètre.
mic = ch.pick_source("microphone")
level = asyncio.run(ch.mic_level(mic))
print(level)  # {'rms': 0.01, 'rms_dbfs': -40.0, 'peak': 0.03, 'peak_dbfs': -30.4}
```

Par HTTP (avec l'extra `[api]` en cours d'exécution) :

```bash
uvicorn capture_helper.api:app --port 8000
curl -o thumb.jpg 'http://localhost:8000/preview/camera.jpg?output_width=480'
curl 'http://localhost:8000/preview/mic-level'      # {"rms":...,"rms_dbfs":...}
# Flux MJPEG : ouvrir dans un navigateur <img src="http://localhost:8000/preview/camera.mjpeg">
```

## Le configurateur de scène navigateur (`/gui`)

```bash
pip install 'capture-helper[api]'
uvicorn capture_helper.api:app --port 8000
# ouvrez http://localhost:8000/gui  (ou simplement http://localhost:8000/)
```

Énumérez vos caméras / microphones, cliquez pour les déposer sur le canevas,
prévisualisez chaque caméra en direct (MJPEG) et chaque micro (vumètre),
glissez pour les arranger, puis **Save scene (JSON)** : le `.scene.json`
téléchargé est exactement ce que consomment `capture-helper scene-validate`,
`scene-show` et `ch.load_scene(...)`. Voir [GUI.md](GUI.md) pour le mode
d'emploi complet. Tout est local : aucun envoi, aucune télémétrie.

## Feuille de route : ce que chaque version débloque

| Version | Couche | Nouvelle capacité |
|---|---|---|
| v0.0.1 | Ossature INPUT | `list_sources` + types |
| **v0.1.0** | INPUT | `pick_source`, `iter_camera_frames`, `iter_mic_audio`, `ffmpeg_input_args`, `MicFrame` |
| **v0.3.0** (celle-ci) | SCÈNES + GUI | Modèle de scène (`new_scene`/`add_source`/`save_scene`/`load_scene`/`resolve_scene_sources`), primitives d'aperçu live (`snapshot_jpeg`/`iter_camera_jpeg`/`mic_level`) et le configurateur de scène navigateur sur `/gui` |
| suivante | INPUT étendu | Capture écran / fenêtre + chaîne de filtres basique (porte de bruit, gain, mise à l'échelle) |
| plus tard | PROCESS | `mix_audio([sources], levels=[...])`, `compose_video([sources], layout=...)` qui joue une scène enregistrée vers une sortie unique |
