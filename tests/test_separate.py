"""Stem separation, with a fake separator instead of Demucs (no model download)."""

import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from click.testing import CliRunner

from soloslot import separate as separate_mod
from soloslot.cli import main
from soloslot.config import ConfigError, load_config
from tests.conftest import SR

STEMS = ("drums", "bass", "guitar", "piano")


@pytest.fixture
def song(tmp_path: Path) -> Path:
    path = tmp_path / "Song.mp3"
    sf.write(path, np.full((SR * 10, 2), 0.1, dtype=np.float32), SR)
    return path


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Replace Demucs: every stem is a constant 0.1 for the length of the input."""
    seen: list[Path] = []

    def load(model: str):
        def split(path: Path):
            seen.append(path)
            frames = sf.info(path).frames
            audio = np.full((frames, 2), 0.1, dtype=np.float32)
            return {name: audio for name in STEMS}, SR

        return split

    monkeypatch.setattr(separate_mod, "load_separator", load)
    return seen


def level(path: Path, start: float, end: float) -> float:
    audio, _ = sf.read(path)
    return float(np.abs(audio[int(start * SR) : int(end * SR)]).max())


def run(*args: object):
    return CliRunner().invoke(main, [str(a) for a in args])


def test_mute_one_instrument_in_the_solo(song: Path, calls: list[Path]) -> None:
    result = run(song, "--solo", "0:02-0:06", "--mute", "guitar")
    assert result.exit_code == 0, result.output
    out = song.parent / "out" / "Song"
    assert level(out / "guitar.wav", 3, 5) == 0.0
    assert level(out / "guitar.wav", 7, 9) > 0.09  # only the solo is muted
    for stem in ("drums", "bass", "piano"):
        assert level(out / f"{stem}.wav", 3, 5) > 0.09
    mix = out / "Song - Backing Track.wav"
    assert abs(level(mix, 3, 5) - 0.3) < 0.01
    assert abs(level(mix, 7, 9) - 0.4) < 0.01
    # the unprocessed stems are kept as well
    assert sorted(p.stem for p in (out / "separated" / "htdemucs_6s").glob("*.flac")) == sorted(
        STEMS
    )


def test_hear_keeps_only_the_named_stems(song: Path, calls: list[Path]) -> None:
    result = run(song, "--solo", "2-6", "--hear", "piano,bass", "--format", "flac")
    assert result.exit_code == 0, result.output
    out = song.parent / "out" / "Song"
    assert level(out / "drums.flac", 3, 5) == 0.0
    assert level(out / "guitar.flac", 3, 5) == 0.0
    assert level(out / "piano.flac", 3, 5) > 0.09
    assert (out / "Song - Backing Track.flac").exists()


def test_several_solos_and_output_folder(song: Path, calls: list[Path], tmp_path: Path) -> None:
    out = tmp_path / "practice"
    result = run(song, "--solo", "1-2", "--solo", "5-7", "--mute", "guitar", "-o", out)
    assert result.exit_code == 0, result.output
    assert level(out / "guitar.wav", 1.2, 1.8) == 0.0
    assert level(out / "guitar.wav", 5.2, 6.8) == 0.0
    assert level(out / "guitar.wav", 3, 4) > 0.09


def test_separation_is_reused_until_the_input_changes(song: Path, calls: list[Path]) -> None:
    run(song, "--solo", "2-6", "--mute", "guitar")
    result = run(song, "--solo", "3-4", "--mute", "piano")
    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    assert "using separated stems" in result.output

    sf.write(song, np.full((SR * 8, 2), 0.1, dtype=np.float32), SR)  # a different recording
    run(song, "--solo", "2-6", "--mute", "guitar")
    assert len(calls) == 2


def test_dry_run_shows_the_model_stems_and_writes_nothing(song: Path, calls: list[Path]) -> None:
    result = run(song, "--solo", "2-6", "--mute", "gitar", "--dry-run")
    assert result.exit_code == 0, result.output
    assert "would separate" in result.output
    assert "WARNING" in result.output and "gitar" in result.output
    assert "stays audible: guitar" in result.output
    assert not calls
    assert not (song.parent / "out").exists()


def test_missing_demucs_explains_how_to_install(
    song: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "demucs.api", None)  # import fails
    result = run(song, "--solo", "2-6", "--mute", "guitar")
    assert result.exit_code == 1
    assert "[separate]" in result.output


def test_separated_stems_are_lowered_instead_of_clipping(tmp_path: Path, song: Path) -> None:
    def load(model: str):
        loud = np.full((SR, 2), 1.5, dtype=np.float32)
        return lambda path: ({"drums": loud, "bass": loud * 0.5}, SR)

    folder = tmp_path / "sep"
    separate_mod.separate(song, folder, "htdemucs", log=lambda _: None, load=load)
    drums, _ = sf.read(folder / "drums.flac")
    bass, _ = sf.read(folder / "bass.flac")
    assert np.max(np.abs(drums)) == pytest.approx(0.99, abs=1e-3)
    assert np.max(np.abs(bass)) == pytest.approx(0.495, abs=1e-3)  # same gain for every stem


def test_audio_file_needs_a_solo(song: Path) -> None:
    result = run(song, "--mute", "guitar")
    assert result.exit_code != 0
    assert "--solo" in result.output


def test_song_options_need_an_audio_file(tmp_path: Path) -> None:
    cfg = tmp_path / "solo.toml"
    cfg.write_text("solos = [ { start = 1, end = 2 } ]\n", encoding="utf-8")
    result = run(cfg, "--solo", "1-2")
    assert result.exit_code != 0
    assert "audio files" in result.output


def test_invalid_solo_option(song: Path) -> None:
    result = run(song, "--solo", "2:15")
    assert result.exit_code != 0
    assert "START-END" in result.output


def test_config_with_input(song: Path, calls: list[Path]) -> None:
    cfg = song.parent / "solo.toml"
    cfg.write_text(
        'input = "Song.mp3"\nmute = ["guitar"]\nsolos = [ { start = 2, end = 6 } ]\n',
        encoding="utf-8",
    )
    (loaded,) = load_config(cfg)
    assert loaded.name == "Song"
    assert loaded.folder == song.parent / "out" / "separated" / "htdemucs_6s"
    result = run(cfg)
    assert result.exit_code == 0, result.output
    assert level(song.parent / "out" / "guitar.wav", 3, 5) == 0.0
    assert level(song.parent / "out" / "piano.wav", 3, 5) > 0.09


def test_song_table_with_input_and_model(tmp_path: Path) -> None:
    cfg = tmp_path / "songs.toml"
    cfg.write_text(
        """
[defaults]
hear = ["bass"]
model = "htdemucs_ft"

[[song]]
input = "songs/Blues.flac"
mute = ["vocals"]
solos = [ { start = 2, end = 6 } ]
""",
        encoding="utf-8",
    )
    (song,) = load_config(cfg)
    assert song.name == "Blues"
    assert song.input == tmp_path.resolve() / "songs" / "Blues.flac"
    assert song.folder == tmp_path.resolve() / "out" / "Blues" / "separated" / "htdemucs_ft"
    assert song.mute == ("vocals",)
    assert song.hear == ()  # the song's 'mute' replaces 'hear' from [defaults]


@pytest.mark.parametrize(
    "body",
    [
        'input = "a.mp3"\nfolder = "."\n',
        'hear = ["bass"]\nmute = ["guitar"]\n',
        'mute = "guitar"\nhear = 3\n',
    ],
)
def test_invalid_input_configs(tmp_path: Path, body: str) -> None:
    cfg = tmp_path / "solo.toml"
    cfg.write_text(body + "solos = [ { start = 1, end = 2 } ]\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(cfg)


def test_backing_only_writes_just_the_backing_track(song: Path, calls: list[Path]) -> None:
    result = run(song, "--solo", "2-6", "--mute", "guitar", "--backing-only")
    assert result.exit_code == 0, result.output
    out = song.parent / "out" / "Song"
    assert sorted(p.name for p in out.glob("*.wav")) == ["Song - Backing Track.wav"]
    assert abs(level(out / "Song - Backing Track.wav", 3, 5) - 0.3) < 0.01
    assert abs(level(out / "Song - Backing Track.wav", 7, 9) - 0.4) < 0.01


def test_config_stems_off_and_nothing_to_write(tmp_path: Path) -> None:
    cfg = tmp_path / "solo.toml"
    body = "solos = [ { start = 1, end = 2 } ]\nstems = false\n"
    cfg.write_text(body, encoding="utf-8")
    assert load_config(cfg)[0].write_stems is False
    cfg.write_text(body + "mixdown = false\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(cfg)


def test_separate_only_writes_stems_but_no_backing_track(song: Path, calls: list[Path]) -> None:
    result = run(song, "--separate-only")
    assert result.exit_code == 0, result.output
    folder = song.parent / "out" / "Song" / "separated" / "htdemucs_6s"
    assert sorted(p.stem for p in folder.glob("*.flac")) == sorted(STEMS)
    assert not list((song.parent / "out" / "Song").glob("*Backing Track*"))
    assert "Stems:" in result.output
    assert len(calls) == 1
    run(song, "--solo", "2-6", "--mute", "guitar")  # the later full run reuses the stems
    assert len(calls) == 1


@pytest.mark.parametrize("extra", [["--solo", "1-2"], ["--mute", "guitar"], ["--dry-run"]])
def test_separate_only_rejects_backing_track_options(
    song: Path, calls: list[Path], extra: list[str]
) -> None:
    result = run(song, "--separate-only", *extra)
    assert result.exit_code == 2
    assert not calls
