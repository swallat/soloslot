"""GUI-independent logic: turn form values into a Song. Testable without Qt."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from soloslot.audio import stem_label
from soloslot.config import ConfigError, Solo, Song, parse_time, song_from_audio
from soloslot.process import find_audio_files
from soloslot.separate import DEFAULT_MODEL, MODEL_STEMS, is_cached

# Shown when the stems of an audio file are not known yet (they depend on the model).
DEFAULT_STEMS = MODEL_STEMS[DEFAULT_MODEL]


@dataclass(frozen=True)
class Form:
    """What the user entered in the window."""

    source: Path | None  # audio file to separate, or a folder with stems
    solos: str  # one region per line: START-END, e.g. 2:15-3:40
    muted: tuple[str, ...]  # stems that are silent in the solo
    output: Path | None = None
    fmt: str = "wav"
    backing_only: bool = False
    model: str = DEFAULT_MODEL


def parse_regions(text: str) -> list[dict[str, str]]:
    """'2:15-3:40' per line (also separated by ';' or ',') -> [{'start':..,'end':..}]."""
    regions = []
    for line in text.replace(";", "\n").replace(",", "\n").splitlines():
        line = line.strip()
        if not line:
            continue
        start, sep, end = line.partition("-")
        if not sep or not start.strip() or not end.strip():
            raise ConfigError(f"expected START-END, e.g. 2:15-3:40, not {line!r}")
        parse_time(start), parse_time(end)  # validate early
        regions.append({"start": start.strip(), "end": end.strip()})
    if not regions:
        raise ConfigError("enter at least one solo region, e.g. 2:15-3:40")
    return regions


def stems_of(source: Path | None, model: str = DEFAULT_MODEL) -> tuple[str, ...]:
    """Stem names offered for muting."""
    if source is None:
        return ()
    if source.is_dir():
        return tuple(stem_label(f) for f in find_audio_files(source))
    return MODEL_STEMS.get(model, ())


def separated_stems(
    source: Path | None, output: Path | None = None, model: str = DEFAULT_MODEL
) -> Path | None:
    """The folder with the stems of an audio file, if it was split before (same file and model).

    This is where a run stores them, so the player can use them without splitting again.
    """
    if source is None or not source.is_file():
        return None
    song = song_from_audio(source, [{"start": 0, "end": 1}], output=output, model=model)
    return song.folder if is_cached(source, song.folder, model) else None


def build_song(form: Form) -> Song:
    if form.source is None:
        raise ConfigError("choose an audio file or a stems folder")
    if not form.muted:
        raise ConfigError("select at least one stem to mute in the solo")
    regions = parse_regions(form.solos)
    if form.source.is_dir():
        folder = form.source.resolve()
        output = (form.output or folder.parent / "out" / folder.name).resolve()
        return Song(
            name=folder.name,
            folder=folder,
            output=output,
            solos=tuple(Solo(parse_time(r["start"]), parse_time(r["end"])) for r in regions),
            mute=form.muted,
            write_stems=not form.backing_only,
            format=form.fmt,
        )
    options = {"model": form.model, "format": form.fmt}
    if form.backing_only:
        options["stems"] = False
    return song_from_audio(form.source, regions, mute=form.muted, output=form.output, **options)


def cli_args(form: Form) -> list[str]:
    """The `soloslot` command line for an audio-file form (used to run separation externally)."""
    song = build_song(form)  # validates the form
    assert form.source is not None
    args = [str(form.source)]
    for solo in parse_regions(form.solos):
        args += ["--solo", f"{solo['start']}-{solo['end']}"]
    args += ["--mute", ",".join(form.muted), "--model", form.model, "--format", form.fmt]
    args += ["--output", str(song.output)]
    if form.backing_only:
        args.append("--backing-only")
    return args


def backing_track_path(song: Song) -> Path:
    """Where `process_song` writes the backing track."""
    return song.output / f"{song.name} - Backing Track.{song.format}"


def reveal_command(path: Path, platform: str = sys.platform) -> list[str] | None:
    """File manager command that opens the folder with `path` selected, if the OS has one.

    Linux has no portable way to select a file, so None means: just open the folder.
    """
    if platform == "win32":
        return ["explorer", f"/select,{path}"]
    if platform == "darwin":
        return ["open", "-R", str(path)]
    return None
