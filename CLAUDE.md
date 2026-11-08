# stem-solo-gap

CLI that silences a solo region in stem WAVs and writes a play-along backing track.

## Layout
- `src/stem_solo_gap/`: `config.py` (TOML, validation), `audio.py` (pure helpers),
  `process.py` (one song, file I/O), `cli.py` (click).
- Tests go in `tests/` and use synthetic audio only; never commit real audio (`*.wav` is ignored).

## Workflow
- `mise run install` once, then `mise run check` (ruff + pytest) before committing.
- Python and packages are managed by uv (`.python-version`, `uv.lock`); mise only provides uv.
