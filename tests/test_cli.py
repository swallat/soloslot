from pathlib import Path

import numpy as np
import pytest
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


def test_reads_mp3_and_flac_and_writes_wav(tmp_path: Path) -> None:
    folder = tmp_path / "stems" / "Song"
    folder.mkdir(parents=True)
    audio = np.full((SR * 10, 2), 0.1, dtype=np.float32)
    sf.write(folder / "Song-Bass-F minor-112bpm-440hz.mp3", audio, SR)
    sf.write(folder / "Song-Winds-F minor-112bpm-440hz.flac", audio, SR, "PCM_24")
    # same base name as the FLAC: WAV wins, the FLAC must not be mixed in twice
    sf.write(folder / "Song-Winds-F minor-112bpm-440hz.wav", audio, SR, "PCM_16")

    result = run(tmp_path)
    assert result.exit_code == 0, result.output
    out = tmp_path / "out" / "Song"
    assert sorted(p.name for p in out.glob("*.wav")) == [
        "Song - Backing Track.wav",
        "Song-Bass-F minor-112bpm-440hz.wav",
        "Song-Winds-F minor-112bpm-440hz.wav",
    ]
    assert sf.info(out / "Song-Bass-F minor-112bpm-440hz.wav").subtype == "PCM_24"  # from MP3
    assert sf.info(out / "Song-Winds-F minor-112bpm-440hz.wav").subtype == "PCM_16"  # WAV kept
    assert level(out / "Song-Winds-F minor-112bpm-440hz.wav", 3, 5) == 0.0


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


SINGLE = """
hear = ["piano", "bass"]
skip = ["visualizer"]
fade_ms = 5
solos = [ { start = 2, end = 6 } ]
"""


def test_runs_in_stems_folder_with_default_solo_toml(
    stems_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (stems_dir / "solo.toml").write_text(SINGLE, encoding="utf-8")
    monkeypatch.chdir(stems_dir)
    result = CliRunner().invoke(main, [])
    assert result.exit_code == 0, result.output
    out = stems_dir / "out"  # next to the stems, no extra song sub folder
    title = "Song (Official Visualizer)"
    assert level(out / moises_name(title, "Guitars"), 3, 5) == 0.0
    assert level(out / moises_name(title, "Bass"), 3, 5) > 0.09
    assert (out / "Song - Backing Track.wav").exists()  # name defaults to the folder name


def test_rerun_does_not_pick_up_its_own_output(
    stems_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (stems_dir / "solo.toml").write_text(SINGLE, encoding="utf-8")
    monkeypatch.chdir(stems_dir)
    CliRunner().invoke(main, [])
    result = CliRunner().invoke(main, [])
    assert result.exit_code == 0
    assert result.output.count("silent in solo") == 3  # drums, guitars, winds; nothing from out/


def test_several_configs_in_one_call(tmp_path: Path, stems_dir: Path) -> None:
    second = tmp_path / "stems" / "Two"
    second.mkdir()
    for f in stems_dir.glob("*.wav"):
        (second / f.name).write_bytes(f.read_bytes())
    (stems_dir / "solo.toml").write_text(SINGLE, encoding="utf-8")
    (second / "solo.toml").write_text(SINGLE, encoding="utf-8")
    result = CliRunner().invoke(main, [str(stems_dir / "solo.toml"), str(second / "solo.toml")])
    assert result.exit_code == 0, result.output
    assert "2 song(s) ok" in result.output
    assert (stems_dir / "out" / "Song - Backing Track.wav").exists()
    assert (second / "out" / "Two - Backing Track.wav").exists()


def test_no_args_and_no_solo_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, [])
    assert result.exit_code != 0
    assert "solo.toml" in result.output


def test_flac_output(tmp_path: Path, stems_dir: Path) -> None:
    cfg = tmp_path / "songs.toml"
    cfg.write_text(CONFIG.replace("fade_ms = 5", 'fade_ms = 5\nformat = "flac"'), encoding="utf-8")
    result = CliRunner().invoke(main, [str(cfg)])
    assert result.exit_code == 0, result.output
    out = tmp_path / "out" / "Song"
    title = "Song (Official Visualizer)"
    bass = out / f"{moises_name(title, 'Bass')[:-4]}.flac"
    assert sf.info(bass).format == "FLAC"
    assert sf.info(bass).subtype == "PCM_24"
    assert level(out / f"{moises_name(title, 'Guitars')[:-4]}.flac", 3, 5) == 0.0
    assert sf.info(out / "Song - Backing Track.flac").format == "FLAC"
    assert not list(out.glob("*.wav"))


def test_originals_are_never_overwritten(tmp_path: Path, stems_dir: Path) -> None:
    before = {p.name: p.read_bytes() for p in stems_dir.iterdir()}
    run(tmp_path)
    assert {p.name: p.read_bytes() for p in stems_dir.iterdir()} == before


def test_output_equal_to_stems_folder_is_refused(tmp_path: Path, stems_dir: Path) -> None:
    cfg = tmp_path / "songs.toml"
    cfg.write_text(
        """
[[song]]
name = "Song"
folder = "stems/Song"
output = "stems"
solos = [ { start = 2, end = 6 } ]
""",
        encoding="utf-8",
    )
    # output = "stems" + name "Song" == the stems folder itself
    before = {p.name: p.read_bytes() for p in stems_dir.iterdir()}
    result = CliRunner().invoke(main, [str(cfg)])
    assert result.exit_code == 1
    assert "output folder is the stems folder" in result.output
    assert {p.name: p.read_bytes() for p in stems_dir.iterdir()} == before


def test_single_song_output_dot_is_refused(
    stems_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (stems_dir / "solo.toml").write_text(SINGLE + 'output = "."\n', encoding="utf-8")
    monkeypatch.chdir(stems_dir)
    result = CliRunner().invoke(main, [])
    assert result.exit_code == 1
    assert "output folder is the stems folder" in result.output
