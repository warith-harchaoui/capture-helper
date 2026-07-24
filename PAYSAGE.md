# Paysage

🇫🇷 Français · [🇬🇧 LANDSCAPE.md](https://github.com/warith-harchaoui/capture-helper/blob/main/LANDSCAPE.md)

Outils voisins et concurrents dans l'espace « capturer caméras /
microphones / écrans sur n'importe quel OS depuis Python », comparés à
`capture-helper`. Les notes vont de ⭐ (1) à ⭐⭐⭐⭐⭐ (5), évaluées sur
la tâche visée par `capture-helper` — une couche de capture **en forme
de bibliothèque**, **pensée pour les pipelines d'IA**, dotée d'un
**configurateur de scène dans le navigateur**, qui se compose avec le
reste de la pile AI Helpers (`video-helper`, `podcast-helper`). Un
projet optimisé pour un tout autre usage (par ex. une application de
streaming de bureau complète) n'est pas pénalisé — la note reflète
seulement l'adéquation à *ce* créneau.

## En un coup d'œil

<!-- TABLE:START -->
| Capture en direct | Énumération multi-OS | Caméra en numpy | Micro en trames PCM | Natif ffmpeg | Streaming en direct | Ergonomie pipelines d'IA | Sans interface |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **capture-helper** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| OpenCV | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| PyAV | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| sounddevice | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| pyaudio | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| mss | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| GUI de streaming de bureau | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ |
| FFmpeg CLI | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| GStreamer | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
<!-- TABLE:END -->

## Carte de positionnement

<!-- FIGURE:START -->
Représentation 2D du tableau ci-dessus.

![Carte de positionnement](https://raw.githubusercontent.com/warith-harchaoui/capture-helper/main/assets/paysage.png)

La carte est un résumé en 2D des 7 critères : à lire comme une forme, pas comme un classement. « capture-helper » se situe dans le coin en haut à droite. Les axes se lisent **Horizontal — Simplicité ↔ Flexibilité** et **Vertical — Rapidité ↔ Ergonomie**.
<!-- FIGURE:END -->

## Positionnement

`capture-helper` se place volontairement à l'intersection de
l'**ergonomie OpenCV / PyAV pour les caméras** (trames BGR numpy) et de
l'**ergonomie sounddevice pour les microphones** (trames PCM float32),
tout en gardant le moteur de capture **entièrement piloté par ffmpeg**
— aucune extension C maison, aucune dépendance à portaudio, aucune
application de bureau séparée à maintenir en vie. Le catalogue de
périphériques et le constructeur d'arguments d'entrée sont
multi-plateformes dans une seule base de code, si bien que les outils de
plus haut niveau (VAD, ASR, ML embarqué) peuvent consommer une caméra ou
un micro en direct via la **même forme d'itérateur que les versions
sur fichier** `video_helper.extract_frames` /
`podcast_helper.extract_audio_stream`. C'est le principal différenciateur
face à toutes les alternatives du tableau ci-dessus.

Chaque alternative porte des nuances que les étoiles compressent. Le
`cv2.VideoCapture` d'OpenCV n'a pas d'API d'énumération — on adresse les
caméras par simple index — mais renvoie un ndarray BGR natif. PyAV
expose des liaisons `avdevice` qui atteignent tous les backends au prix
d'une mise en place rugueuse et propre à chaque OS. sounddevice et
pyaudio reposent sur portaudio et ne traitent que l'audio,
respectivement par callback et en mode bloquant. mss (avec pyautogui /
`ImageGrab` de Pillow) capture l'écran en ndarray RGB mais ne voit ni
caméra ni microphone. Les GUI de streaming de bureau excellent au
RTMP / HLS / enregistrement complet et se scriptent via une API
WebSocket, mais exigent que l'application de bureau reste active et ne
vous rendent pas les trames brutes. La CLI FFmpeg brute énumère avec
`-list_devices` et diffuse partout, mais vous laisse le remodelage et le
typage Python à charge. GStreamer avec PyGObject est un pipeline
Linux-first à faible latence, avec `rtmpsink` / `hlssink` prêts à
l'emploi, plus lourd à installer et moins portable.

## Quand choisir quoi

- **`capture-helper`** — capture sans interface, Python d'abord, pour
  les pipelines d'IA : énumération multi-plateforme + trames BGR numpy
  + trames PCM asynchrones, se compose avec le reste de la suite AI
  Helpers.
- **OpenCV `cv2.VideoCapture`** — vous avez déjà OpenCV et n'avez
  besoin que des caméras, pas des micros, sans les commodités
  d'énumération multi-OS.
- **PyAV** — vous voulez un accès direct à libav et acceptez de vous
  battre avec `avdevice` par OS.
- **sounddevice / soundcard** — micro seulement, portaudio acceptable,
  pas de vidéo.
- **pyaudio** — micro seulement, lectures portaudio bloquantes, pas de
  vidéo.
- **mss / ImageGrab** — captures d'écran seulement, ni caméra ni audio.
- **GUI de streaming de bureau** — vous exécutez déjà une application de
  streaming de bureau complète et voulez scripter les changements de
  scène via son API WebSocket, pas consommer des trames brutes en
  Python.
- **FFmpeg CLI (brute)** — vous voulez zéro dépendance Python et
  acceptez d'écrire vous-même le remodelage et la plomberie.
- **GStreamer + PyGObject** — pipelines Linux-first à faible latence
  avec RTMP / HLS prêts à l'emploi ; plus lourd à installer, moins
  portable.
