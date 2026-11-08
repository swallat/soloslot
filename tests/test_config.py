from pathlib import Path

import pytest

from soloslot.config import ConfigError, load_config, parse_time


@pytest.mark.parametrize(
    ("value", "expected"),
    [(12, 12.0), (1.5, 1.5), ("135.5", 135.5), ("2:15", 135.0), ("1:02:15.5", 3735.5)],
)
def test_parse_time(value: object, expected: float) -> None:
    assert parse_time(value) == expected


@pytest.mark.parametrize("value", ["abc", "1:x", True])
def test_parse_time_invalid(value: object) -> None:
    with pytest.raises(ConfigError):
        parse_time(value)


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "songs.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_bars_are_converted_with_bpm(tmp_path: Path) -> None:
    cfg = write(
        tmp_path,
        """
[[song]]
name = "A"
folder = "stems/A"
bpm = 120
solos = [ { start_bar = 3, end_bar = 5 } ]
""",
    )
    (song,) = load_config(cfg)
    assert song.solos[0].start == pytest.approx(4.0)  # 2 bars * 2 s
    assert song.solos[0].end == pytest.approx(8.0)
    assert song.folder == tmp_path.resolve() / "stems/A"  # relative to the config file


def test_defaults_and_song_override(tmp_path: Path) -> None:
    cfg = write(
        tmp_path,
        """
[defaults]
hear = ["piano"]
fade_ms = 10

[[song]]
name = "A"
folder = "a"
solos = [ { start = "0:10", end = "0:20" } ]

[[song]]
name = "B"
folder = "b"
hear = ["bass"]
solos = [ { start = 1, end = 2 } ]
""",
    )
    a, b = load_config(cfg)
    assert a.hear == ("piano",)
    assert b.hear == ("bass",)
    assert a.fade_ms == b.fade_ms == 10.0


@pytest.mark.parametrize(
    "solos",
    [
        "[]",
        "[ { start = 5 } ]",
        "[ { start = 9, end = 3 } ]",
        "[ { start_bar = 2, end_bar = 4 } ]",  # no bpm
        "[ { foo = 1 } ]",
    ],
)
def test_invalid_solos(tmp_path: Path, solos: str) -> None:
    cfg = write(tmp_path, f'[[song]]\nname = "A"\nfolder = "a"\nsolos = {solos}\n')
    with pytest.raises(ConfigError):
        load_config(cfg)


def test_no_songs(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(write(tmp_path, "[defaults]\n"))


def test_single_song_layout_defaults(tmp_path: Path) -> None:
    folder = tmp_path / "My Song"
    folder.mkdir()
    cfg = folder / "solo.toml"
    cfg.write_text('hear = ["piano"]\nsolos = [ { start = "0:10", end = "0:20" } ]\n')
    (song,) = load_config(cfg)
    assert song.name == "My Song"
    assert song.folder.resolve() == folder.resolve()
    assert song.output == folder.resolve() / "out"
    assert song.hear == ("piano",)


def test_single_song_with_defaults_table(tmp_path: Path) -> None:
    cfg = write(tmp_path, "[defaults]\nfade_ms = 7\n\nsolos = [ { start = 1, end = 2 } ]\n")
    # `solos` after a table header belongs to [defaults]; hoist it to the top level instead
    cfg.write_text("solos = [ { start = 1, end = 2 } ]\n\n[defaults]\nfade_ms = 7\n")
    (song,) = load_config(cfg)
    assert song.fade_ms == 7.0


def test_mixing_song_tables_and_top_level_solos_is_an_error(tmp_path: Path) -> None:
    cfg = write(
        tmp_path,
        'solos = [ { start = 1, end = 2 } ]\n\n[[song]]\nname = "A"\nfolder = "a"\n'
        "solos = [ { start = 1, end = 2 } ]\n",
    )
    with pytest.raises(ConfigError):
        load_config(cfg)


def test_format_defaults_to_wav_and_accepts_flac(tmp_path: Path) -> None:
    cfg = write(tmp_path, 'solos = [ { start = 1, end = 2 } ]\nformat = ".FLAC"\n')
    assert load_config(cfg)[0].format == "flac"
    cfg = write(tmp_path, "solos = [ { start = 1, end = 2 } ]\n")
    assert load_config(cfg)[0].format == "wav"


def test_mp3_format_is_accepted(tmp_path: Path) -> None:
    cfg = write(tmp_path, 'solos = [ { start = 1, end = 2 } ]\nformat = "MP3"\n')
    assert load_config(cfg)[0].format == "mp3"


def test_invalid_format(tmp_path: Path) -> None:
    cfg = write(tmp_path, 'solos = [ { start = 1, end = 2 } ]\nformat = "ogg"\n')
    with pytest.raises(ConfigError):
        load_config(cfg)
