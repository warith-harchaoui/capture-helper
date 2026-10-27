# Paysage

🇫🇷 Français · [🇬🇧 LANDSCAPE.md](https://github.com/warith-harchaoui/capture-helper/blob/main/LANDSCAPE.md)

Outils voisins et concurrents dans l'espace « capturer caméras,
microphones et écrans sur n'importe quel système depuis Python », comparés
à `capture-helper`. Les notes vont de ⭐ (1) à ⭐⭐⭐⭐⭐ (5), évaluées sur
la tâche visée par `capture-helper` : une couche de capture **en forme
de bibliothèque**, **pensée pour les pipelines d'IA**, dotée d'un
**configurateur de scène dans le navigateur**, qui se compose avec le
reste de la pile AI Helpers (`video-helper`, `podcast-helper`). Un
projet optimisé pour un tout autre usage, une application de bureau de
streaming complète par exemple, n'est pas pénalisé : la note reflète
seulement l'adéquation à *ce* créneau.

## En un coup d'œil

<!-- TABLE:START -->
| Capture en direct | Énumération multi-OS | Caméra en numpy | Micro en trames PCM | Natif ffmpeg | Streaming en direct | Ergonomie pipelines d'IA | Sans interface |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **capture-helper** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| OpenCV | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| PyAV | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| sounddevice | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| PyAudio | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| mss | ⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| VidGear | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| OBS Studio | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ |
| FFmpeg CLI | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| GStreamer | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
<!-- TABLE:END -->

## Carte de positionnement

<!-- FIGURE:START -->
Représentation 2D du tableau ci-dessus.

![Carte de positionnement](https://raw.githubusercontent.com/warith-harchaoui/capture-helper/main/assets/paysage.png)

La carte est un résumé en 2D des sept critères : à lire comme une forme, pas comme un classement. « capture-helper » se situe dans le coin en haut à droite. Les axes se lisent **Horizontal : Autonomie ↔ Maîtrise** et **Vertical : Adaptabilité ↔ Efficacité**.
<!-- FIGURE:END -->

## Positionnement

`capture-helper` se place volontairement à l'intersection de
l'**ergonomie OpenCV / PyAV pour les caméras** (trames BGR numpy) et de
l'**ergonomie sounddevice pour les microphones** (trames PCM float32),
tout en gardant le moteur de capture **entièrement piloté par ffmpeg** :
aucune extension C maison, aucune dépendance à portaudio, aucune
application de bureau séparée à maintenir en vie. Le catalogue de
périphériques et le constructeur d'arguments d'entrée sont
multiplateformes dans une seule base de code, si bien que les outils de
plus haut niveau (VAD, ASR, ML embarqué) peuvent consommer une caméra ou
un micro en direct via la **même forme d'itérateur que les versions
sur fichier** `video_helper.extract_frames` /
`podcast_helper.extract_audio_stream`. C'est le principal différenciateur
face à toutes les alternatives du tableau ci-dessus.

Chaque alternative porte des nuances que les étoiles compressent. Le
`cv2.VideoCapture` d'OpenCV n'a pas d'API d'énumération (on adresse les
caméras par simple index) mais renvoie un ndarray BGR natif. PyAV
expose des liaisons `avdevice` qui atteignent tous les backends au prix
d'une mise en place rugueuse et propre à chaque OS. sounddevice et
pyaudio reposent sur portaudio et ne traitent que l'audio,
respectivement par callback et en mode bloquant. mss (avec pyautogui ou
`ImageGrab` de Pillow) capture l'écran en ndarray RGB mais ne voit ni
caméra ni microphone. VidGear enveloppe OpenCV pour les trames caméra et
superpose un streaming piloté par FFmpeg (`WriteGear` / `StreamGear`), si
bien qu'il capture et diffuse bien la vidéo mais n'expose aucun chemin
microphone. OBS Studio excelle au RTMP / HLS / enregistrement complet et
se script via son API WebSocket, mais exige que l'application de bureau
reste active et ne vous rend pas les trames brutes. La CLI FFmpeg brute
énumère avec `-list_devices` et diffuse partout, mais vous laisse le
remodelage et le typage Python à charge. GStreamer avec PyGObject est
un pipeline Linux-first à faible latence, avec `rtmpsink` / `hlssink`
prêts à l'emploi, plus lourd à installer et moins portable.

## Quand choisir quoi

- **`capture-helper`** : capture sans interface, Python d'abord, pour
  les pipelines d'IA, énumération multiplateforme, trames BGR numpy,
  trames PCM asynchrones, composition avec le reste de la suite AI
  Helpers.
- **OpenCV `cv2.VideoCapture`** : vous avez déjà OpenCV et n'avez
  besoin que des caméras, pas des micros, sans les commodités
  d'énumération multi-OS.
- **PyAV** : vous voulez un accès direct à libav et acceptez de vous
  battre avec `avdevice` par OS.
- **sounddevice** : micro seulement, lectures portaudio par callback,
  pas de vidéo.
- **PyAudio** : micro seulement, lectures portaudio bloquantes, pas de
  vidéo.
- **mss** : captures d'écran seulement, ni caméra ni audio.
- **VidGear** : vous voulez un framework vidéo performant adossé à
  OpenCV avec streaming FFmpeg intégré ; caméras seulement, aucun chemin
  microphone.
- **OBS Studio** : vous exécutez déjà l'application de streaming de
  bureau complète et voulez scripter les changements de scène via son
  API WebSocket, pas consommer des trames brutes en Python.
- **FFmpeg CLI (brute)** : vous voulez zéro dépendance Python et
  acceptez d'écrire vous-même le remodelage et la plomberie.
- **GStreamer + PyGObject** : pipelines Linux-first à faible latence
  avec RTMP / HLS prêts à l'emploi, plus lourd à installer, moins
  portable.

## Sources et date de relevé

Les étoiles jugent l'**adéquation à ce créneau**, elles ne mesurent rien :
aucun chronométrage n'a été fait et aucun débit n'est avancé. Ce qui a été
vérifié, c'est la *capacité* derrière chaque colonne — quel projet énumère les
périphériques, lequel renvoie un tableau numpy, lequel possède un chemin
microphone — face à la documentation de chaque projet, le **2026-10-27**. Les
API de capture bougent lentement, mais il suffirait qu'un projet ajoute un gear
microphone ou un appel d'énumération pour qu'une ligne de ce tableau se trompe
au sujet d'autrui : la date fait donc partie de l'affirmation.

- [Module `videoio` d'OpenCV](https://github.com/opencv/opencv/tree/4.x/modules/videoio) — les backends de `VideoCapture` ; les caméras s'adressent par simple index, sans point d'entrée d'énumération
- [Documentation de PyAV](https://pyav.org/docs/stable/) — les liaisons libav, entrées périphériques comprises
- [Documentation de python-sounddevice](https://python-sounddevice.readthedocs.io/) — adossée à PortAudio, audio seulement, orientée callback
- [Documentation de PyAudio](https://people.csail.mit.edu/hubert/pyaudio/docs/) — adossée à PortAudio, audio seulement, lectures bloquantes
- [Documentation de python-mss](https://python-mss.readthedocs.io/) — écran seulement : ni caméra ni audio
- [Les gears de VidGear](https://abhitronix.github.io/vidgear/latest/gears/) — la liste complète des gears, d'où vient le « aucun chemin microphone »
- [obs-websocket](https://github.com/obsproject/obs-websocket) — la surface de scriptage qu'expose OBS Studio, avec ce qu'elle rend et ce qu'elle ne rend pas
- [Documentation des périphériques FFmpeg](https://ffmpeg.org/ffmpeg-devices.html) — `avfoundation`, `dshow`, `v4l2`, `pulse`, `alsa` et le drapeau `-list_devices` que ce paquet appelle en sous-main
- [Liaisons Python de GStreamer](https://gstreamer.freedesktop.org/bindings/python.html) — PyGObject, l'installation que ce tableau qualifie de plus lourde

La ligne de `capture-helper` ne vient d'aucun document : elle se lit dans le
code de ce dépôt, à la version inscrite dans `pyproject.toml`.
