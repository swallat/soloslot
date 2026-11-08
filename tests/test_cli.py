from pathlib import Path

import numpy as np
import soundfile as sf
from click.testing import CliRunner

from stem_solo_gap import __version__
from stem_solo_gap.cli import main
from tests.conftest import SR, STEMS, moises_name

CONFIG = """
[defaults]
hear = ["piano", "bass"]
skip = ["visualizer"]
fade_ms = 5

[[song]]
name = "Song"
folder = "stems/Song"
solos = [ { start = 2, end = 6 } ]
"""


def run(tmp_path: Path, *args: str):
    cfg = tmp_path / "songs.toml"
    cfg.write_text(CONFIG, encoding="utf-8")
    return CliRunner().invoke(main, [str(cfg), *args])


def level(path: Path, start: float, end: float) -> float:
    audio, _ = sf.read(path)
    return float(np.abs(audio[int(start * SR) : int(end * SR)]).max())


def test_version() -> None:
    result = CliRunner().invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_clears_solo_in_unselected_stems(tmp_path: Path, stems_dir: Path) -> None:
    result = run(tmp_path)
    assert result.exit_code == 0, result.output
    out = tmp_path / "out" / "Song"
    title = "Song (Official Visualizer)"
    assert level(out / moises_name(title, "Guitars"), 3, 5) == 0.0
    assert level(out / moises_name(title, "Winds"), 3, 5) == 0.0
    assert level(out / moises_name(title, "Grand Piano"), 3, 5) > 0.09
    assert level(out / moises_name(title, "Bass"), 3, 5) > 0.09
    assert level(out / moises_name(title, "Guitars"), 7, 9) > 0.09  # audible outside the solo
    assert not (out / "Song (Official Visualizer).wav").exists()  # full mix is skipped
    assert sf.info(out / moises_name(title, "Bass")).subtype == "PCM_24"  # format preserved


def test_backing_track_contains_only_audible_stems_in_solo(tmp_path: Path, stems_dir: Path) -> None:
    run(tmp_path)
    mix = tmp_path / "out" / "Song" / "Song - Backing Track.wav"
    assert abs(level(mix, 3, 5) - 0.2) < 0.01  # piano + bass (0.1 each); drums are silent too
    assert abs(level(mix, 7, 9) - 0.1 * len(STEMS)) < 0.01  # all five stems outside the solo


def test_dry_run_writes_nothing(tmp_path: Path, stems_dir: Path) -> None:
    result = run(tmp_path, "--dry-run")
    assert result.exit_code == 0
    assert not (tmp_path / "out").exists()


def test_hear_typo_is_reported(tmp_path: Path, stems_dir: Path) -> None:
    cfg = tmp_path / "songs.toml"
    cfg.write_text(CONFIG.replace('"bass"', '"bsas"'), encoding="utf-8")
    result = CliRunner().invoke(main, [str(cfg), "--dry-run"])
    assert "WARNING" in result.output and "bsas" in result.output


def test_missing_folder_fails(tmp_path: Path) -> None:
    result = run(tmp_path)
    assert result.exit_code == 1
    assert "folder not found" in result.output


def test_unknown_song(tmp_path: Path, stems_dir: Path) -> None:
    result = run(tmp_path, "--song", "Nope")
    assert result.exit_code != 0
    assert "not found" in result.output
