"""Command line interface."""

from __future__ import annotations

from pathlib import Path

import click

from stem_solo_gap import __version__
from stem_solo_gap.config import ConfigError, load_config
from stem_solo_gap.process import process_song

DEFAULT_CONFIG = "solo.toml"


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("configs", nargs=-1, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--song", "only", metavar="NAME", help="Process only this song (name from the config)."
)
@click.option("--dry-run", is_flag=True, help="Show what would happen, write nothing.")
@click.version_option(__version__, prog_name="stem-solo-gap")
def main(configs: tuple[Path, ...], only: str | None, dry_run: bool) -> None:
    """Silence a solo section in stem files and build a play-along backing track.

    CONFIGS are TOML files describing solo regions and which stems stay audible in
    the solo. A file holds either one song (put it next to the stems) or several
    [[song]] tables. Without arguments, ./solo.toml is used, so you can run the tool
    inside a stems folder. See songs.example.toml and solo.example.toml.
    """
    if not configs:
        default = Path(DEFAULT_CONFIG)
        if not default.is_file():
            raise click.ClickException(
                f"no config given and no ./{DEFAULT_CONFIG} in {Path.cwd()}. "
                "Pass a config file or create one (see solo.example.toml)."
            )
        configs = (default,)

    songs = []
    try:
        for config in configs:
            songs.extend(load_config(config))
    except ConfigError as e:
        raise click.ClickException(str(e)) from e
    if only:
        songs = [s for s in songs if s.name == only]
        if not songs:
            raise click.ClickException(f"song '{only}' not found")

    ok = [process_song(s, dry_run=dry_run, log=click.echo) for s in songs]
    failed = len(ok) - sum(ok)
    click.echo(f"\nDone: {sum(ok)} song(s) ok, {failed} failed.")
    if failed:
        raise SystemExit(1)
