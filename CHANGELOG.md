# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Desktop window `soloslot-gui` (optional `gui` extra) with a collapsible console output.
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

[Unreleased]: https://github.com/swallat/soloslot/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/swallat/soloslot/releases/tag/v0.1.0
