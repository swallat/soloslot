"""Pure audio and stem-name helpers (no file access)."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from soloslot.config import Solo

Audio = NDArray[np.floating]

# Moises names stems "<Title>-<Stem>-<Key>-<tempo>bpm-<hz>hz.wav"
_MOISES_RE = re.compile(r"-(?P<label>[^-]+)-[^-]+-\d+\s*bpm-\d+\s*hz$", re.IGNORECASE)


def stem_label(path: Path) -> str:
    """Lower-case stem name (e.g. 'winds') taken from a file name."""
    m = _MOISES_RE.search(path.stem)
    return (m.group("label") if m else path.stem).strip().lower()


def matches(label: str, names: tuple[str, ...] | list[str]) -> bool:
    """True if any name is a substring of the label (case-insensitive)."""
    return any(n.lower() in label for n in names)


def apply_gaps(audio: Audio, sr: int, solos: tuple[Solo, ...], fade_ms: float) -> Audio:
    """Silence the solo regions, with short fades at the edges to avoid clicks.

    `audio` has shape (frames, channels).
    """
    out = audio.copy()
    n = len(out)
    fade = max(1, int(sr * fade_ms / 1000))
    for solo in solos:
        a = min(max(round(solo.start * sr), 0), n)
        b = min(max(round(solo.end * sr), 0), n)
        if b <= a:
            continue
        out[a:b] = 0
        fa = min(fade, a)  # fade-out ends at the gap
        if fa:
            out[a - fa : a] *= np.linspace(1.0, 0.0, fa, endpoint=False)[:, None]
        fb = min(fade, n - b)  # fade-in starts after the gap
        if fb:
            out[b : b + fb] *= np.linspace(0.0, 1.0, fb, endpoint=False)[:, None]
    return out


def mix_stems(stems: list[Audio]) -> tuple[Audio, float]:
    """Sum stems of possibly different length/channel count.

    Returns the mix and the gain in dB applied to avoid clipping (0.0 if none).
    """
    length = max(len(s) for s in stems)
    channels = max(s.shape[1] for s in stems)
    mix = np.zeros((length, channels), dtype=np.float64)
    for s in stems:
        if s.shape[1] == 1 and channels > 1:
            s = np.repeat(s, channels, axis=1)
        mix[: len(s), : s.shape[1]] += s
    peak = float(np.max(np.abs(mix))) if mix.size else 0.0
    if peak > 0.99:
        gain = 0.99 / peak
        return (mix * gain).astype(np.float32), float(20 * np.log10(gain))
    return mix.astype(np.float32), 0.0
