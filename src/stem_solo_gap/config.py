"""Reading and validating the songs config (TOML)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

OUTPUT_FORMATS = ("wav", "flac")


class ConfigError(ValueError):
    """The config file or one of its songs is invalid."""


@dataclass(frozen=True)
class Solo:
    """A solo region in seconds."""

    start: float
    end: float


@dataclass(frozen=True)
class Song:
    name: str
    folder: Path
    output: Path
    solos: tuple[Solo, ...]
    hear: tuple[str, ...] = ()
    skip: tuple[str, ...] = ()
    fade_ms: float = 30.0
    mixdown: bool = True
    format: str = "wav"
    notes: list[str] = field(default_factory=list, compare=False)


def parse_time(value: Any) -> float:
    """Seconds from a number, '135.5', '2:15' or '1:02:15.5'."""
    if isinstance(value, bool):
        raise ConfigError(f"invalid time: {value!r}")
    if isinstance(value, int | float):
        return float(value)
    seconds = 0.0
    try:
        for part in str(value).strip().split(":"):
            seconds = seconds * 60 + float(part)
    except ValueError:
        raise ConfigError(f"invalid time: {value!r}") from None
    return seconds


def _solos(raw: dict[str, Any], name: str) -> tuple[Solo, ...]:
    entries = raw.get("solos") or []
    if not entries:
        raise ConfigError(f"{name}: 'solos' is missing or empty")
    sec_per_bar = None
    solos: list[Solo] = []
    for entry in entries:
        if "start" in entry or "end" in entry:
            if "start" not in entry or "end" not in entry:
                raise ConfigError(f"{name}: 'start' and 'end' belong together")
            start, end = parse_time(entry["start"]), parse_time(entry["end"])
        elif "start_bar" in entry or "end_bar" in entry:
            if "start_bar" not in entry or "end_bar" not in entry:
                raise ConfigError(f"{name}: 'start_bar' and 'end_bar' belong together")
            if "bpm" not in raw:
                raise ConfigError(f"{name}: bars need 'bpm' on the song")
            if sec_per_bar is None:
                beats = float(raw.get("beats_per_bar", 4))
                sec_per_bar = beats * 60.0 / float(raw["bpm"])
            offset = parse_time(raw.get("offset", 0))
            start = offset + (float(entry["start_bar"]) - 1) * sec_per_bar
            end = offset + (float(entry["end_bar"]) - 1) * sec_per_bar
        else:
            raise ConfigError(f"{name}: a solo needs start/end or start_bar/end_bar")
        if end <= start:
            raise ConfigError(f"{name}: solo end {end:.2f}s is not after start {start:.2f}s")
        solos.append(Solo(start, end))
    return tuple(solos)


def _song(raw: dict[str, Any], defaults: dict[str, Any], base: Path, *, single: bool) -> Song:
    merged = {**defaults, **raw}
    if single:
        # One song per config file: the stems live next to the config by default.
        folder = base / str(raw.get("folder", "."))
        name = str(raw.get("name", folder.resolve().name))
        output = base / str(merged.get("output", "out"))
    else:
        if "name" not in raw or "folder" not in raw:
            raise ConfigError("every [[song]] needs 'name' and 'folder'")
        name = str(raw["name"])
        folder = base / str(raw["folder"])
        output = base / str(merged.get("output", "out")) / name
    fmt = str(merged.get("format", "wav")).lower().lstrip(".")
    if fmt not in OUTPUT_FORMATS:
        raise ConfigError(f"{name}: format must be one of {', '.join(OUTPUT_FORMATS)}, not {fmt!r}")
    return Song(
        name=name,
        folder=folder,
        output=output,
        solos=_solos(raw, name),
        hear=tuple(merged.get("hear", ())),
        skip=tuple(merged.get("skip", ())),
        fade_ms=float(merged.get("fade_ms", 30)),
        mixdown=bool(merged.get("mixdown", True)),
        format=fmt,
    )


def load_config(path: Path) -> list[Song]:
    """Load the songs of a config file. Relative paths resolve against the config's directory.

    Two layouts are accepted:
    - several songs: `[[song]]` tables, each with `name` and `folder`;
    - one song: `solos` (and optional `hear`, `bpm`, ...) at the top level. `folder` defaults
      to the config's directory, `name` to that directory's name, and output goes to `out/`.
    """
    try:
        with path.open("rb") as fh:
            cfg = tomllib.load(fh)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from e
    base = path.resolve().parent
    defaults = cfg.get("defaults", {})
    raw_songs = cfg.get("song", [])

    if raw_songs and "solos" in cfg:
        raise ConfigError(f"{path}: use either [[song]] tables or a top-level 'solos', not both")
    if raw_songs:
        return [_song(raw, defaults, base, single=False) for raw in raw_songs]
    if "solos" in cfg:
        top = {k: v for k, v in cfg.items() if k != "defaults"}
        return [_song(top, defaults, base, single=True)]
    raise ConfigError(f"{path}: no [[song]] entries and no top-level 'solos'")
