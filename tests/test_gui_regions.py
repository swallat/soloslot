import numpy as np
import pytest
import soundfile as sf

from soloslot.config import Solo
from soloslot.gui import regions as rg


def test_format_time_roundtrips_through_parse_time():
    from soloslot.config import parse_time

    for seconds in (0, 5, 65, 135.25, 3725.5):
        assert parse_time(rg.format_time(seconds)) == pytest.approx(seconds)
    assert rg.format_time(135) == "2:15"
    assert rg.format_time(135.5) == "2:15.5"


def test_text_roundtrip_and_lenient_parsing():
    slots = [Solo(65, 108), Solo(150.5, 190)]
    assert rg.text_to_slots(rg.slots_to_text(slots)) == slots
    # half-typed or invalid lines are skipped, not fatal
    assert rg.text_to_slots("1:00-\nabc\n2:00-1:00\n3:00-3:30") == [Solo(180, 210)]


def test_clamp_and_move_keep_slots_inside_the_song():
    assert rg.clamp_slot(50, 10, 100) == Solo(10, 50)
    assert rg.clamp_slot(-5, 120, 100) == Solo(0, 100)
    assert rg.clamp_slot(10, 10, 100).end - 10 == pytest.approx(rg.MIN_SLOT)
    assert rg.move_slot(Solo(10, 20), -50, 100) == Solo(0, 10)
    assert rg.move_slot(Solo(10, 20), 500, 100) == Solo(90, 100)


def test_hit_test_prefers_edges_over_body():
    slots = [Solo(10, 20), Solo(30, 40)]
    assert rg.hit_test(slots, 10.2, 0.5) == (0, "start")
    assert rg.hit_test(slots, 19.9, 0.5) == (0, "end")
    assert rg.hit_test(slots, 15, 0.5) == (0, "body")
    assert rg.hit_test(slots, 25, 0.5) is None


def test_preview_span_pads_and_clamps():
    assert rg.preview_span(Solo(10, 20), 100, 3) == (7, 23)
    assert rg.preview_span(Solo(1, 99), 100, 3) == (0, 100)


def test_peaks_shape_and_values():
    audio = np.zeros((1000, 2), dtype="float32")
    audio[500:510] = 0.5
    p = rg.peaks(audio, 10)
    assert p.shape == (10, 2)
    assert p[5, 1] == pytest.approx(0.5)
    assert p[0, 1] == 0


def _stems(tmp_path):
    for name, level in (("piano", 0.2), ("bass", 0.1)):
        sf.write(tmp_path / f"{name}.wav", np.full((44100, 2), level, dtype="float32"), 44100)
    return rg.load_stems(tmp_path)


def test_render_silences_muted_stems_inside_slots_only(tmp_path):
    stems = _stems(tmp_path)
    assert stems.duration == pytest.approx(1.0)
    assert stems.can_mute
    slots = [Solo(0.4, 0.6)]
    original = rg.render(stems, ("piano",), slots, 30, gaps=False)
    gapped = rg.render(stems, ("piano",), slots, 30, gaps=True)
    assert original[22050, 0] == pytest.approx(0.3, abs=1e-3)
    assert gapped[22050, 0] == pytest.approx(0.1, abs=1e-3)  # only bass remains in the slot
    assert gapped[0, 0] == pytest.approx(0.3, abs=1e-3)
    assert rg.matches_any(stems.labels, ("piano",))
    assert not rg.matches_any(stems.labels, ("drums",))


def test_load_stems_rejects_mixed_sample_rates(tmp_path):
    from soloslot.config import ConfigError

    sf.write(tmp_path / "a.wav", np.zeros((100, 2), dtype="float32"), 44100)
    sf.write(tmp_path / "b.wav", np.zeros((100, 2), dtype="float32"), 48000)
    with pytest.raises(ConfigError):
        rg.load_stems(tmp_path)


def test_single_file_cannot_be_muted(tmp_path):
    f = tmp_path / "song.wav"
    sf.write(f, np.zeros((100, 2), dtype="float32"), 44100)
    assert not rg.load_stems(f).can_mute
