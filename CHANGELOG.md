# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-08

### Added
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

[Unreleased]: https://github.com/swallat/stem-solo-gap/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/swallat/stem-solo-gap/commits/main
