# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Drop `setup.py` (sole source of truth is `pyproject.toml`).
- Add GitHub Actions CI.

## [0.0.1] - 2026-06-28

Initial scaffold.

### Features at release

- Type-only scaffolding for the OBS-inspired capture/process/publish
  pipeline (Inputs → Process → Publish).
- Cross-platform device enumeration: camera / microphone / screen /
  window.

### Roadmap

- v0.1 — capture sources (iter_camera_frames, iter_mic_audio,
  iter_screen_frames, iter_window_frames)
- v0.2 — filter chains (noise gate, gain, chroma key, scale)
- v0.3 — multi-source mixer
- v0.4 — RTMP / HLS / Icecast publish (live YouTube / Twitch / podcast)
- v0.5 — virtual webcam / virtual microphone outputs
- v0.6 — OBS WebSocket bidirectional control
