from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from soloslot.config import ConfigError
from soloslot.gui.model import Form, build_song, parse_regions, stems_of


def test_parse_regions():
    assert parse_regions("2:15-3:40\n1:00-1:30; 90-100") == [
        {"start": "2:15", "end": "3:40"},
        {"start": "1:00", "end": "1:30"},
        {"start": "90", "end": "100"},
    ]


@pytest.mark.parametrize("text", ["", "  \n", "2:15", "abc-def", "-3:00"])
def test_parse_regions_invalid(text):
    with pytest.raises(ConfigError):
        parse_regions(text)


def _stems(folder: Path) -> None:
    folder.mkdir()
    for name in ("piano", "bass"):
        sf.write(folder / f"{name}.wav", np.zeros((4410, 2), dtype="float32"), 44100)


def test_build_song_from_folder(tmp_path):
    _stems(tmp_path / "tune")
    song = build_song(
        Form(tmp_path / "tune", "0:00-0:01", ("piano",), backing_only=True, fmt="flac")
    )
    assert song.name == "tune"
    assert song.mute == ("piano",)
    assert not song.write_stems
    assert song.format == "flac"
    assert song.output == (tmp_path / "out" / "tune").resolve()
    assert stems_of(tmp_path / "tune") == ("bass", "piano")


def test_build_song_from_audio(tmp_path):
    audio = tmp_path / "song.wav"
    sf.write(audio, np.zeros((4410, 2), dtype="float32"), 44100)
    song = build_song(Form(audio, "10-20", ("guitar",), output=tmp_path / "o"))
    assert song.input == audio.resolve()
    assert song.output == (tmp_path / "o").resolve()
    assert "guitar" in stems_of(audio)


def test_build_song_needs_input_and_mute(tmp_path):
    with pytest.raises(ConfigError, match="choose"):
        build_song(Form(None, "1-2", ("a",)))
    with pytest.raises(ConfigError, match="mute"):
        build_song(Form(tmp_path, "1-2", ()))
