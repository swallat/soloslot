from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

SR = 8000  # low rate keeps the tests fast
STEMS = ["Bass", "Drums", "Grand Piano", "Guitars", "Winds"]


def moises_name(title: str, stem: str) -> str:
    return f"{title}-{stem}-F minor-112bpm-440hz.wav"


@pytest.fixture
def stems_dir(tmp_path: Path) -> Path:
    """A song folder with 10 s constant-level stems and a full-mix file."""
    folder = tmp_path / "stems" / "Song"
    folder.mkdir(parents=True)
    audio = np.full((SR * 10, 2), 0.1, dtype=np.float32)
    for stem in STEMS:
        sf.write(folder / moises_name("Song (Official Visualizer)", stem), audio, SR, "PCM_24")
    sf.write(folder / "Song (Official Visualizer).wav", audio, SR, "PCM_24")
    return folder
