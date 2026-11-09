from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from soloslot.config import ConfigError
from soloslot.gui.model import Form, build_song, cli_args, parse_regions, stems_of


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


def test_cli_args(tmp_path):
    audio = tmp_path / "song.wav"
    sf.write(audio, np.zeros((4410, 2), dtype="float32"), 44100)
    form = Form(audio, "2:15-3:40\n5:00-5:20", ("guitar", "piano"), fmt="flac", backing_only=True)
    args = cli_args(form)
    assert args[0] == str(audio)
    assert args.count("--solo") == 2
    assert args[args.index("--mute") + 1] == "guitar,piano"
    assert "--backing-only" in args
    assert args[args.index("--output") + 1] == str((tmp_path / "out" / "song").resolve())


def test_reveal_command():
    from pathlib import Path

    from soloslot.gui.model import reveal_command

    p = Path("out/a - Backing Track.wav")
    assert reveal_command(p, "win32") == ["explorer", f"/select,{p}"]
    assert reveal_command(p, "darwin") == ["open", "-R", str(p)]
    assert reveal_command(p, "linux") is None


def test_separated_stems_finds_only_a_finished_split_of_this_file(tmp_path):
    import json

    from soloslot.gui.model import separated_stems
    from soloslot.separate import DEFAULT_MODEL, _fingerprint

    song = tmp_path / "tune.mp3"
    song.write_bytes(b"x" * 10)
    assert separated_stems(song) is None  # never split
    assert separated_stems(None) is None and separated_stems(tmp_path) is None
    folder = tmp_path / "out" / "tune" / "separated" / DEFAULT_MODEL
    folder.mkdir(parents=True)
    assert separated_stems(song) is None  # no marker: not finished
    (folder / "source.json").write_text(json.dumps(_fingerprint(song, DEFAULT_MODEL)))
    assert separated_stems(song) == folder
    song.write_bytes(b"y" * 20)  # another file under the same name
    assert separated_stems(song) is None
