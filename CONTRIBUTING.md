# Contributing

Thanks for your interest! Bug reports, ideas and pull requests are welcome.

## Reporting bugs and ideas

Open an [issue](https://github.com/swallat/soloslot/issues/new/choose). For a bug,
please include:

- the command you ran and the full output,
- your config file (remove anything private),
- the file format of your stems (WAV, FLAC, MP3, sample rate, bit depth),
- your OS and `soloslot --version`.

Please **do not attach copyrighted audio**. Describe the files instead.

## Development setup

[mise](https://mise.jdx.dev) provides `uv`; `uv` manages Python and the packages.

```bash
mise install       # installs uv
mise run install   # uv sync
mise run check     # ruff + pytest
```

Without mise, `uv sync` and `uv run pytest` work the same way.

## Pull requests

1. Fork, then create a branch from `main`.
2. Keep the change focused. Add or update tests; they use synthetic audio only (see
   `tests/conftest.py`). Never commit real audio: `*.wav`, `*.mp3` and `*.flac` are git-ignored.
3. Run `mise run check` (or `uv run ruff check . && uv run ruff format --check . && uv run pytest`).
   CI runs the same on Linux, Windows and macOS.
4. Update the README, `solo.example.toml` / `songs.example.toml` and `CHANGELOG.md` if behaviour
   or config options change.
5. Open the pull request and describe what changed and why.

By contributing you agree that your contribution is licensed under the [MIT License](LICENSE).

## Releasing

1. Move the `Unreleased` entries in `CHANGELOG.md` under a new version heading and bump
   `version` in `pyproject.toml`.
2. Merge that change to `main`, then tag it: `git tag v0.1.0 && git push origin v0.1.0`.
3. The `Release` workflow checks that the tag matches the version, runs the tests, builds the
   package, publishes to PyPI via Trusted Publishing, builds the desktop installers
   (`installers.yml`: Windows, macOS, Linux) and creates the GitHub release with the packages,
   the installers and `SHA256SUMS`. The in-app update check relies on those asset names, see
   `platform_suffix` in `src/soloslot/update.py`.

The installers can be test-built without a release: run the `Installers` workflow manually
or change anything under `packaging/` in a pull request. Locally: `packaging/build.sh`.
