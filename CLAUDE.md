# soloslot

CLI that mutes chosen stems in a solo region and writes a play-along backing track. A full
song can be split into stems first with Demucs (optional `separate` extra).

## Layout
- `src/soloslot/`: `config.py` (TOML, validation), `audio.py` (pure helpers),
  `process.py` (one song, file I/O), `separate.py` (Demucs, imported lazily), `cli.py` (click).
- Config: either `[[song]]` tables (many songs) or top-level `solos` (one song, stems next to the
  config; default `./solo.toml`). `Song.output` is the final output directory.
- Tests never load Demucs: they replace `separate.load_separator` with a fake (see
  `tests/test_separate.py`).
- Tests go in `tests/` and use synthetic audio only; never commit real audio (`*.wav` is ignored).

## Workflow
- `mise run install` once, then `mise run check` (ruff + pytest) before committing.
- Python and packages are managed by uv (`.python-version`, `uv.lock`); mise only provides uv.
