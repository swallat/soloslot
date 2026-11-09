# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed
- Player: after a single song was split, the player kept showing the song and A/B stayed off. It
  now loads the split stems when the run finishes, and also when a song that was split before is
  chosen again (same file and model), so A/B and the stem view work right away.
- Player: the waveform result of loading was handled on the worker thread; it now arrives on the
  GUI thread.

## [0.4.4] - 2026-11-09

### Added
- Player: the usual transport buttons (previous, back 5 s, play/pause, stop, forward 5 s, next).
  Previous and next jump between the slot starts.
- Player: A/B comparison of the original and the result with gaps. The A/B button (or the B key)
  switches at the same position without a gap or restart; both versions are kept in memory.
- GUI: an Open output folder button after a successful run.

### Fixed
- Windows installer: the notices page showed raw Markdown (`#`, `**`, `<links>`). The installer now
  shows a plain-text version generated at build time.

### Changed
- CI: Ubuntu runners are pinned to 26.04 LTS (the AppImage is still built on 22.04).

## [0.4.3] - 2026-11-09

### Fixed
- App setup on Windows still failed with `os error 448` because Windows refuses to follow the
  junction uv creates for the Python minor-version link, whatever the folder. The setup now
  removes such stale links and, when uv fails on the link, creates the environment from the
  already unpacked `cpython-<version>` folder by its exact path (no download, no link).

### Changed
- Added a notice that soloslot may only be used with material the user has the rights to, in the
  README, the license/notices page (Help > About, AppImage docs) and as an extra Windows installer
  page that also shows the third-party licenses.

## [0.4.2] - 2026-11-09

### Fixed
- Windows installer: upgrading left the old bundle files in place, including the old
  `soloslot-<version>.dist-info`. The window then still showed the previous version (and kept
  offering the update) although the new code ran. The installer now clears `_internal` first.
- App setup on Windows failed with `os error 448` (untrusted mount point) while uv linked its
  Python: the setup now uses the resolved real path and retries in `C:\Users\Public\soloslot`.

## [0.4.1] - 2026-11-09

### Fixed
- App setup failed with uv 0.13 (`UV_MANAGED_PYTHON` cannot be used with `--python-preference`):
  the setup now sets only `UV_MANAGED_PYTHON` and clears conflicting user uv Python variables.

## [0.4.0] - 2026-11-08

### Added
- Player in the window: waveform of the song or stems, solo slots drawn, moved and resized with
  the mouse (kept in sync with the solo list), playback with the original or the result with
  gaps, an optional "Show stems" view with one waveform per stem, and "Preview slot" to check the
  start and end of a slot. Uses `sounddevice` (PortAudio).

### Fixed
- Installed app: the stem separation setup no longer picks up the user's own Python or uv
  configuration (it failed on a scoop-managed Python on Windows). uv now uses its own Python
  and cache in the app data folder.

### Changed
- Installers show the logo: Windows setup wizard images, macOS disk image volume icon and
  Applications shortcut.
- The separation environment uses Python 3.13 (3.12 on Intel Macs, where Demucs needs an old
  PyTorch).

## [0.3.0] - 2026-11-08

### Added
- MP3 as output format (`--format mp3`, `format = "mp3"`, GUI format list).
- The installed desktop app can now split full songs: on first use it downloads `uv`
  (checksum verified), creates a private Python environment in the user's data folder and
  installs `soloslot[separate]` (CPU PyTorch on Linux). Separation runs there and its output
  streams into the Details section.
- Window and installers carry the soloslot logo: header, window and taskbar icon, Windows `.ico`,
  macOS `.icns`, AppImage icon.
- Help > About dialog with version, author, links and a Licenses tab. License notices for Qt,
  PySide6, Demucs, PyTorch and the other dependencies (`THIRD_PARTY_NOTICES.md`) ship inside the
  app and next to it in the Windows installer and the AppImage.
- Help > Check for updates… checks on demand and says when soloslot is up to date.

### Changed
- README shows screenshots (`packaging/screenshots.py` renders them offscreen).
- Window design follows the logo: amber accent for the main action, focus and progress,
  Fusion style for the same look on every platform, labelled inputs, larger click targets.

## [0.2.0] - 2026-11-08

### Added
- Desktop window `soloslot-gui` (optional `gui` extra) with a collapsible console output.
- Update notice in the window: checks GitHub Releases at startup (one request, can be turned
  off with `SOLOSLOT_NO_UPDATE_CHECK=1`). The installed app downloads the installer and verifies
  its SHA256 before opening it; other installs get a link to the release page.
- Release workflow builds installers: Windows setup `.exe`, macOS `.dmg` (Apple Silicon), Linux
  `.AppImage`, plus `SHA256SUMS`. They are unsigned and do not bundle PyTorch/Demucs.

## [0.1.0] - 2026-11-08

First release on PyPI. Formerly developed as stem-solo-gap, now named **soloslot** (package,
command and module).

### Added
- Stem separation with Demucs (optional `separate` extra): give a full song (MP3, WAV, FLAC,
  ...) instead of a stems folder, on the command line or as `input` in the config. Default
  model `htdemucs_6s` (drums, bass, guitar, piano, vocals, other); choose another with `model`.
- Command line mode for one song: `soloslot song.mp3 --solo 2:15-3:40 --mute guitar`, with
  `--solo` (repeatable), `--hear`, `--mute`, `--model`, `--format` and `--output`.
- `mute` as the opposite of `hear`: name the stems to silence in the solo, the rest stays.
- `--backing-only` / `stems = false` to write only the backing track.
- Separated stems are cached in the output folder and reused until the input file changes.
- Silence one or more solo regions in stem files and write the stems plus a mixed
  `<song> - Backing Track`.
- `hear` / `skip` to choose which stems stay audible in the solo and which files are ignored;
  a `hear` entry that matches no stem is reported as a warning.
- Solo regions as timestamps (`start`/`end`) or bars (`start_bar`/`end_bar` with `bpm`).
- Input as WAV, FLAC or MP3; output as WAV or FLAC (`format`).
- One config per song (default `./solo.toml`, run inside the stems folder) or one config with
  several `[[song]]` tables; several configs can be passed in one call.
- `--song` to pick a song and `--dry-run` to preview.
- Refuses an output folder that equals the stems folder, so originals are never overwritten.

[Unreleased]: https://github.com/swallat/soloslot/compare/v0.4.4...HEAD
[0.4.4]: https://github.com/swallat/soloslot/compare/v0.4.3...v0.4.4
[0.4.3]: https://github.com/swallat/soloslot/compare/v0.4.1...v0.4.3
[0.4.1]: https://github.com/swallat/soloslot/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/swallat/soloslot/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/swallat/soloslot/releases/tag/v0.3.0
[0.2.0]: https://github.com/swallat/soloslot/releases/tag/v0.2.0
[0.1.0]: https://github.com/swallat/soloslot/releases/tag/v0.1.0
