"""Process one song: read stems, clear the solo, write stems and backing track."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import soundfile as sf

from stem_solo_gap.audio import apply_gaps, matches, mix_stems, stem_label
from stem_solo_gap.config import Song

AUDIO_EXTENSIONS = (".wav", ".flac", ".mp3")  # in order of preference
_LOSSLESS_SUBTYPES = {"PCM_16", "PCM_24", "PCM_32", "FLOAT", "DOUBLE"}


def find_audio_files(folder: Path) -> list[Path]:
    """Audio files in `folder`, one per base name (WAV preferred over FLAC over MP3)."""
    chosen: dict[str, Path] = {}
    for ext in reversed(AUDIO_EXTENSIONS):
        for f in folder.iterdir():
            if f.is_file() and f.suffix.lower() == ext:
                chosen[f.stem] = f
    return sorted(chosen.values())


def output_subtype(input_subtype: str) -> str:
    """Keep the input's PCM format; lossy or unusual inputs become 24 bit PCM."""
    return input_subtype if input_subtype in _LOSSLESS_SUBTYPES else "PCM_24"


def process_song(song: Song, *, dry_run: bool = False, log: Callable[[str], None] = print) -> bool:
    """Process one song. Returns False (after logging why) if it could not be done."""
    log(f"\n=== {song.name} ===")
    if not song.folder.is_dir():
        log(f"  ERROR: folder not found: {song.folder}")
        return False
    for solo in song.solos:
        log(f"  Solo: {solo.start:7.2f}s - {solo.end:7.2f}s  ({solo.end - solo.start:.1f}s)")

    stems = []
    for f in find_audio_files(song.folder):
        label = stem_label(f)
        if song.skip and matches(label, song.skip):
            log(f"  skipped: {f.name}")
            continue
        stems.append((f, label))
    if not stems:
        log(f"  ERROR: no audio files found ({', '.join(AUDIO_EXTENSIONS)})")
        return False

    # A typo in 'hear' would silently mute a stem, so report unmatched entries.
    for h in song.hear:
        if not any(h.lower() in label for _, label in stems):
            log(f"  WARNING: 'hear' entry '{h}' matches no stem of this song")

    out_dir = song.output
    sample_rate = None
    results = []
    for f, label in stems:
        info = sf.info(f)
        audio, sr = sf.read(f, dtype="float32", always_2d=True)
        if sample_rate is None:
            sample_rate = sr
        elif sr != sample_rate:
            log(f"  ERROR: {f.name} has {sr} Hz, expected {sample_rate} Hz")
            return False
        audible = matches(label, song.hear)
        result = audio if audible else apply_gaps(audio, sr, song.solos, song.fade_ms)
        log(f"  {'stays audible' if audible else 'silent in solo'}: {label}")
        results.append(result)
        if not dry_run:
            out_dir.mkdir(parents=True, exist_ok=True)
            sf.write(out_dir / f"{f.stem}.wav", result, sr, subtype=output_subtype(info.subtype))

    if song.mixdown and sample_rate is not None:
        mix, gain_db = mix_stems(results)
        if gain_db:
            log(f"  Mix would clip, lowered by {-gain_db:.1f} dB")
        if not dry_run:
            path = out_dir / f"{song.name} - Backing Track.wav"
            sf.write(path, mix, sample_rate, subtype="PCM_24")
            log(f"  written: {path}")

    if not dry_run:
        log(f"  output: {out_dir.resolve()}")
    return True
