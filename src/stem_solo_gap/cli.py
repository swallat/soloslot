"""Command line interface."""

from __future__ import annotations

from pathlib import Path

import click

from stem_solo_gap import __version__
from stem_solo_gap.config import ConfigError, load_config
from stem_solo_gap.process import process_song


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("config", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--song", "only", metavar="NAME", help="Process only this song (name from the config)."
)
@click.option("--dry-run", is_flag=True, help="Show what would happen, write nothing.")
@click.version_option(__version__, prog_name="stem-solo-gap")
def main(config: Path, only: str | None, dry_run: bool) -> None:
    """Silence a solo section in stem WAVs and build a play-along backing track.

    CONFIG is a TOML file describing songs, solo regions and which stems stay
    audible in the solo. See songs.example.toml.
    """
    try:
        songs = load_config(config)
    except ConfigError as e:
        raise click.ClickException(str(e)) from e
    if only:
        songs = [s for s in songs if s.name == only]
        if not songs:
            raise click.ClickException(f"song '{only}' not found in {config}")

    ok = [process_song(s, dry_run=dry_run, log=click.echo) for s in songs]
    failed = len(ok) - sum(ok)
    click.echo(f"\nDone: {sum(ok)} song(s) ok, {failed} failed.")
    if failed:
        raise SystemExit(1)
