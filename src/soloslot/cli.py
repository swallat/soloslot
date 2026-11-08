"""Command line interface."""

from __future__ import annotations

from pathlib import Path

import click

from soloslot import __version__
from soloslot.config import OUTPUT_FORMATS, ConfigError, load_config, song_from_audio
from soloslot.process import process_song
from soloslot.separate import DEFAULT_MODEL

DEFAULT_CONFIG = "solo.toml"


def _split(values: tuple[str, ...]) -> tuple[str, ...]:
    """'piano,bass' 'drums' -> ('piano', 'bass', 'drums')"""
    return tuple(v.strip() for value in values for v in value.split(",") if v.strip())


def _solo(value: str) -> dict[str, str]:
    start, sep, end = value.partition("-")
    if not sep or not start.strip() or not end.strip():
        raise click.BadParameter(f"expected START-END, e.g. 2:15-3:40, not {value!r}")
    return {"start": start.strip(), "end": end.strip()}


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("inputs", nargs=-1, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--song", "only", metavar="NAME", help="Process only this song (name from the config)."
)
@click.option(
    "--solo",
    "solos",
    multiple=True,
    metavar="START-END",
    help="Solo region of an audio file, e.g. 2:15-3:40 or 135-220. Repeat for several.",
)
@click.option(
    "--hear",
    multiple=True,
    metavar="STEMS",
    help="Stems that stay audible in the solo, e.g. piano,bass,drums. All others are muted.",
)
@click.option(
    "--mute",
    multiple=True,
    metavar="STEMS",
    help="Stems that are muted in the solo, e.g. guitar. All others stay audible.",
)
@click.option(
    "--model",
    default=None,
    metavar="NAME",
    help=f"Demucs model used to split audio files (default: {DEFAULT_MODEL}).",
)
@click.option(
    "--format", "fmt", type=click.Choice(OUTPUT_FORMATS), default=None, help="Output format."
)
@click.option(
    "-o",
    "--output",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Output folder for an audio file (default: out/<song>/ next to it).",
)
@click.option("--dry-run", is_flag=True, help="Show what would happen, write nothing.")
@click.version_option(__version__, prog_name="soloslot")
def main(
    inputs: tuple[Path, ...],
    only: str | None,
    solos: tuple[str, ...],
    hear: tuple[str, ...],
    mute: tuple[str, ...],
    model: str | None,
    fmt: str | None,
    output: Path | None,
    dry_run: bool,
) -> None:
    """Mute instruments in a solo section and build a play-along backing track.

    INPUTS are songs (MP3, WAV, FLAC, ...) or TOML configs.

    \b
    A song is split into stems with Demucs (needs the 'separate' extra):
      soloslot song.mp3 --solo 2:15-3:40 --hear piano,bass,drums
      soloslot song.flac --solo 1:05-2:40 --mute guitar

    A config describes stems you already have, or songs to split (`input = "song.mp3"`).
    A file holds either one song or several [[song]] tables. Without arguments,
    ./solo.toml is used, so you can run the tool inside a stems folder. See
    songs.example.toml and solo.example.toml.
    """
    configs = [p for p in inputs if p.suffix.lower() == ".toml"]
    audio = [p for p in inputs if p.suffix.lower() != ".toml"]
    song_options = solos or hear or mute or model or fmt or output
    if song_options and not audio:
        raise click.UsageError(
            "--solo, --hear, --mute, --model, --format and --output apply to audio files; "
            "put these settings in the config instead"
        )
    if not inputs:
        default = Path(DEFAULT_CONFIG)
        if not default.is_file():
            raise click.ClickException(
                f"no input given and no ./{DEFAULT_CONFIG} in {Path.cwd()}. "
                "Pass a song or a config file (see solo.example.toml)."
            )
        configs = [default]
    if audio and not solos:
        raise click.UsageError("give the solo region of the song with --solo START-END")
    if hear and mute:
        raise click.UsageError("use either --hear or --mute, not both")
    if output and len(audio) > 1:
        raise click.UsageError("--output works with one audio file at a time")

    songs = []
    try:
        for config in configs:
            songs.extend(load_config(config))
        regions = [_solo(s) for s in solos]
        options = {k: v for k, v in (("model", model), ("format", fmt)) if v}
        songs.extend(
            song_from_audio(
                path, regions, hear=_split(hear), mute=_split(mute), output=output, **options
            )
            for path in audio
        )
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
