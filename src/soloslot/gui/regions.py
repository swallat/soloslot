"""Qt-free logic behind the player: solo slots, time text, waveform peaks, preview audio."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from soloslot.audio import Audio, apply_gaps, matches, mix_stems, stem_label
from soloslot.config import ConfigError, Solo, parse_time
from soloslot.process import find_audio_files

MIN_SLOT = 0.1  # seconds; shorter slots are dropped or stretched to this
PREVIEW_PAD = 3.0  # seconds played before and after a slot when previewing it


def format_time(seconds: float) -> str:
    """'2:15' or '2:15.25' (hundredths only when needed); parseable by `parse_time`."""
    cs = round(max(seconds, 0.0) * 100)
    minutes, cs = divmod(cs, 6000)
    secs, cs = divmod(cs, 100)
    text = f"{minutes}:{secs:02d}"
    return f"{text}.{cs:02d}".rstrip("0") if cs else text


def slots_to_text(slots: list[Solo]) -> str:
    return "\n".join(f"{format_time(s.start)}-{format_time(s.end)}" for s in slots)


def text_to_slots(text: str) -> list[Solo]:
    """Valid START-END lines of the solo text; lines that do not parse (yet) are skipped."""
    slots = []
    for line in text.replace(";", "\n").replace(",", "\n").splitlines():
        start, sep, end = line.strip().partition("-")
        if not sep:
            continue
        try:
            a, b = parse_time(start), parse_time(end)
        except ConfigError:
            continue
        if b > a >= 0:
            slots.append(Solo(a, b))
    return slots


def clamp_slot(start: float, end: float, duration: float) -> Solo:
    """Order the ends, keep the slot inside the song and at least MIN_SLOT long."""
    a, b = sorted((start, end))
    a = min(max(a, 0.0), max(duration - MIN_SLOT, 0.0))
    b = min(max(b, a + MIN_SLOT), max(duration, a + MIN_SLOT))
    return Solo(a, b)


def move_slot(slot: Solo, delta: float, duration: float) -> Solo:
    """Shift a slot without changing its length; it stops at the song's edges."""
    length = slot.end - slot.start
    start = min(max(slot.start + delta, 0.0), max(duration - length, 0.0))
    return Solo(start, start + length)


def hit_test(slots: list[Solo], t: float, tolerance: float) -> tuple[int, str] | None:
    """Which slot part is at time `t`: (index, 'start' | 'end' | 'body'), or None.

    Edges win over the body; `tolerance` is the grab distance in seconds.
    """
    best: tuple[float, int, str] | None = None
    for i, s in enumerate(slots):
        for part, edge in (("start", s.start), ("end", s.end)):
            d = abs(t - edge)
            if d <= tolerance and (best is None or d < best[0]):
                best = (d, i, part)
    if best:
        return best[1], best[2]
    for i, s in enumerate(slots):
        if s.start < t < s.end:
            return i, "body"
    return None


def preview_span(slot: Solo, duration: float, pad: float = PREVIEW_PAD) -> tuple[float, float]:
    """What 'preview slot' plays: the slot with `pad` seconds around it."""
    return max(slot.start - pad, 0.0), min(slot.end + pad, duration)


def peaks(audio: Audio, buckets: int) -> np.ndarray:
    """(buckets, 2) array of min and max sample per bucket (channels averaged)."""
    mono = audio.mean(axis=1) if audio.ndim > 1 else audio
    n = len(mono)
    buckets = max(1, min(buckets, n))
    edges = np.linspace(0, n, buckets + 1).astype(int)
    out = np.zeros((buckets, 2), dtype=np.float32)
    for i in range(buckets):
        chunk = mono[edges[i] : max(edges[i + 1], edges[i] + 1)]
        out[i] = chunk.min(), chunk.max()
    return out


@dataclass
class Stems:
    """Decoded stems of one song, for the player."""

    sample_rate: int
    labels: list[str]
    audio: list[Audio]

    @property
    def duration(self) -> float:
        return max((len(a) for a in self.audio), default=0) / self.sample_rate

    @property
    def can_mute(self) -> bool:
        """Muting needs several stems; a single file can only be played as it is."""
        return len(self.audio) > 1


def load_stems(source: Path) -> Stems:
    """Decode a stems folder, or a single audio file as one stem."""
    files = find_audio_files(source) if source.is_dir() else [source]
    if not files:
        raise ConfigError("no audio files found")
    labels, audio, rate = [], [], None
    for f in files:
        data, sr = sf.read(f, dtype="float32", always_2d=True)
        if rate is None:
            rate = sr
        elif sr != rate:
            raise ConfigError(f"{f.name} has {sr} Hz, expected {rate} Hz")
        labels.append(stem_label(f))
        audio.append(data)
    assert rate is not None
    return Stems(rate, labels, audio)


def render(
    stems: Stems, muted: tuple[str, ...], slots: list[Solo], fade_ms: float, gaps: bool
) -> Audio:
    """The mix as it will be written (`gaps`) or the untouched original.

    Same rule as `process_song`: stems matching a `muted` name are silent inside the slots.
    """
    parts = []
    for label, data in zip(stems.labels, stems.audio, strict=True):
        if gaps and slots and matches(label, muted):
            data = apply_gaps(data, stems.sample_rate, tuple(slots), fade_ms)
        parts.append(data)
    mix, _ = mix_stems(parts)
    return mix


def matches_any(labels: list[str], muted: tuple[str, ...]) -> bool:
    """Whether any stem would be muted by the `muted` names."""
    return any(matches(label, muted) for label in labels)


SKIP = 5.0  # seconds moved by rewind and forward


def previous_marker(slots: list[Solo], position: float, margin: float = 0.5) -> float:
    """Where 'previous' goes: the closest slot start before `position`, or the song start."""
    return max((s.start for s in slots if s.start < position - margin), default=0.0)


def next_marker(slots: list[Solo], position: float, duration: float, margin: float = 0.05) -> float:
    """Where 'next' goes: the closest slot start after `position`, or the song end."""
    return min((s.start for s in slots if s.start > position + margin), default=duration)
