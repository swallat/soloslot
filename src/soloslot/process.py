"""Process one song: read stems, clear the solo, write stems and backing track."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import soundfile as sf

from soloslot.audio import apply_gaps, matches, mix_stems, stem_label
from soloslot.config import Song
from soloslot.separate import MODEL_STEMS, SeparationError, is_cached, separate

MP3_SAMPLE_RATES = (8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000)
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


def mp3_supported() -> bool:
    """Whether the bundled libsndfile can encode MP3 (libsndfile 1.1+, in the soundfile wheels)."""
    return "MP3" in sf.available_formats()


def write_audio(path: Path, data, sample_rate: int, fmt: str, subtype: str = "PCM_24") -> None:
    """Write `data` as `fmt`. MP3 is lossy and has no bit depth, so `subtype` is ignored there."""
    if fmt == "mp3":
        sf.write(path, data, sample_rate, format="MP3", subtype="MPEG_LAYER_III")
    else:
        sf.write(path, data, sample_rate, subtype=subtype)


def output_subtype(input_subtype: str, fmt: str = "wav") -> str:
    """Keep the input's bit depth; lossy or unsupported inputs become 24 bit PCM.

    FLAC cannot store float or 32 bit PCM, so those become 24 bit there. MP3 has no bit depth
    (see `write_audio`).
    """
    allowed = _LOSSLESS_SUBTYPES if fmt == "wav" else {"PCM_16", "PCM_24"}
    return input_subtype if input_subtype in allowed else "PCM_24"


def _check_names(song: Song, labels: list[str], log: Callable[[str], None]) -> None:
    # A typo in 'hear' would silently mute a stem (and one in 'mute' keep it), so report it.
    key, names = ("mute", song.mute) if song.mute else ("hear", song.hear)
    for n in names:
        if not any(n.lower() in label for label in labels):
            log(f"  WARNING: '{key}' entry '{n}' matches no stem of this song")


def _silenced(song: Song, label: str) -> bool:
    return matches(label, song.mute) if song.mute else not matches(label, song.hear)


def _separate(song: Song, *, dry_run: bool, log: Callable[[str], None]) -> bool | None:
    """Split `song.input` into `song.folder`. Returns True/False to stop early, None to go on."""
    assert song.input is not None
    if not song.input.is_file():
        log(f"  ERROR: input file not found: {song.input}")
        return False
    if dry_run and not is_cached(song.input, song.folder, song.model):
        # Nothing to read yet: show what the separation would produce.
        labels = list(MODEL_STEMS.get(song.model, ()))
        log(f"  would separate {song.input.name} with Demucs '{song.model}' into {song.folder}")
        for s in song.solos:
            log(f"  Solo: {s.start:7.2f}s - {s.end:7.2f}s  ({s.end - s.start:.1f}s)")
        if labels:
            _check_names(song, labels, log)
            for label in labels:
                log(f"  {'silent in solo' if _silenced(song, label) else 'stays audible'}: {label}")
        return True
    try:
        separate(song.input, song.folder, song.model, log=log)
    except SeparationError as e:
        log(f"  ERROR: {e}")
        return False
    return None


def separate_only(song: Song, *, log: Callable[[str], None] = print) -> bool:
    """Only split `song.input` into stems (no backing track). False if it failed (logged)."""
    log(f"\n=== {song.name} ===")
    if song.input is None:
        log("  ERROR: nothing to separate: the song has no input file")
        return False
    if _separate(song, dry_run=False, log=log) is False:
        return False
    log(f"  Stems: {song.folder}")
    return True


def process_song(song: Song, *, dry_run: bool = False, log: Callable[[str], None] = print) -> bool:
    """Process one song. Returns False (after logging why) if it could not be done."""
    log(f"\n=== {song.name} ===")
    if song.input is not None:
        done = _separate(song, dry_run=dry_run, log=log)
        if done is not None:
            return done
    if not song.folder.is_dir():
        log(f"  ERROR: folder not found: {song.folder}")
        return False
    if song.output.resolve() == song.folder.resolve():
        # Would overwrite the original stems and feed the results back in on the next run.
        log("  ERROR: output folder is the stems folder; choose a different 'output'")
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

    _check_names(song, [label for _, label in stems], log)

    if song.format == "mp3" and not dry_run and not mp3_supported():
        log("  ERROR: this soundfile/libsndfile build cannot write MP3; use wav or flac")
        return False

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
        if song.format == "mp3" and sr not in MP3_SAMPLE_RATES:
            log(f"  ERROR: MP3 cannot store {sr} Hz ({f.name}); use wav or flac")
            return False
        audible = not _silenced(song, label)
        result = audio if audible else apply_gaps(audio, sr, song.solos, song.fade_ms)
        log(f"  {'stays audible' if audible else 'silent in solo'}: {label}")
        results.append(result)
        if song.write_stems and not dry_run:
            out_dir.mkdir(parents=True, exist_ok=True)
            write_audio(
                out_dir / f"{f.stem}.{song.format}",
                result,
                sr,
                song.format,
                output_subtype(info.subtype, song.format),
            )

    if song.mixdown and sample_rate is not None:
        mix, gain_db = mix_stems(results)
        if gain_db:
            log(f"  Mix would clip, lowered by {-gain_db:.1f} dB")
        if not dry_run:
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"{song.name} - Backing Track.{song.format}"
            write_audio(path, mix, sample_rate, song.format)
            log(f"  written: {path}")

    if not dry_run:
        log(f"  output: {out_dir.resolve()}")
    return True
