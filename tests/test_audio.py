from pathlib import Path

import numpy as np
import pytest

from stem_solo_gap.audio import apply_gaps, matches, mix_stems, stem_label
from stem_solo_gap.config import Solo

SR = 1000


def test_stem_label_moises_name() -> None:
    p = Path("Bill Evans - Interplay _Official Visualizer_-Grand Piano-F minor-112bpm-440hz.wav")
    assert stem_label(p) == "grand piano"


def test_stem_label_falls_back_to_file_name() -> None:
    assert stem_label(Path("Drums.wav")) == "drums"


def test_matches_is_case_insensitive_substring() -> None:
    assert matches("grand piano", ["PIANO"])
    assert not matches("bass", ["guitar"])


def test_apply_gaps_silences_region_and_fades_edges() -> None:
    audio = np.ones((SR * 10, 1), dtype=np.float32)
    out = apply_gaps(audio, SR, (Solo(4.0, 6.0),), fade_ms=100)
    assert np.all(out[4 * SR : 6 * SR] == 0)
    assert out[: 3 * SR].min() == 1.0 and out[7 * SR :].min() == 1.0  # untouched away from edges
    assert out[4 * SR - 1, 0] < 0.05  # fade-out reaches ~0 at the gap
    assert out[6 * SR, 0] == 0.0 and out[6 * SR + 99, 0] > 0.95  # fade-in after the gap
    assert audio.min() == 1.0  # input not modified


def test_apply_gaps_clamps_to_file_length() -> None:
    audio = np.ones((SR * 2, 2), dtype=np.float32)
    out = apply_gaps(audio, SR, (Solo(1.5, 99.0), Solo(-5.0, 0.2)), fade_ms=10)
    assert np.all(out[int(1.5 * SR) :] == 0)
    assert np.all(out[: int(0.2 * SR)] == 0)


def test_mix_pads_and_sums() -> None:
    a = np.full((10, 2), 0.2, dtype=np.float32)
    b = np.full((5, 1), 0.1, dtype=np.float32)
    mix, gain_db = mix_stems([a, b])
    assert mix.shape == (10, 2)
    assert mix[0, 0] == pytest.approx(0.3) and mix[9, 0] == pytest.approx(0.2)
    assert gain_db == 0.0


def test_mix_lowers_level_when_clipping() -> None:
    a = np.full((10, 1), 0.8, dtype=np.float32)
    mix, gain_db = mix_stems([a, a])
    assert np.max(np.abs(mix)) == pytest.approx(0.99)
    assert gain_db < 0
