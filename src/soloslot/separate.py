"""Split a full song into stems with Demucs (optional `separate` extra).

Demucs and PyTorch are imported only when a song actually needs separating, so the rest of
the tool works without them.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import soundfile as sf
from numpy.typing import NDArray

DEFAULT_MODEL = "htdemucs_6s"

# Stems each known Demucs model produces. Used for --dry-run and for checking `hear`/`mute`
# before the (slow) separation; other model names are passed to Demucs as they are.
MODEL_STEMS: dict[str, tuple[str, ...]] = {
    "htdemucs_6s": ("drums", "bass", "other", "vocals", "guitar", "piano"),
    "htdemucs": ("drums", "bass", "other", "vocals"),
    "htdemucs_ft": ("drums", "bass", "other", "vocals"),
    "hdemucs_mmi": ("drums", "bass", "other", "vocals"),
    "mdx": ("drums", "bass", "other", "vocals"),
    "mdx_extra": ("drums", "bass", "other", "vocals"),
    "mdx_q": ("drums", "bass", "other", "vocals"),
    "mdx_extra_q": ("drums", "bass", "other", "vocals"),
}

INSTALL_HINT = (
    "stem separation needs the 'separate' extra: "
    "uv tool install 'soloslot[separate] @ git+https://github.com/swallat/soloslot.git'"
)

_MARKER = "source.json"
_EXT = "flac"  # lossless and about half the size of WAV

# (frames, channels) float32 audio per stem name, and the sample rate
Stems = dict[str, NDArray[np.float32]]
Separator = Callable[[Path], tuple[Stems, int]]


class SeparationError(RuntimeError):
    """Separation could not run (Demucs missing, model not available, unreadable input)."""


def load_separator(model: str) -> Separator:
    """Load a Demucs model and return a function that splits one file into stems."""
    try:
        from demucs.api import Separator as DemucsSeparator
    except ImportError as e:
        raise SeparationError(INSTALL_HINT) from e
    try:
        demucs = DemucsSeparator(model=model, progress=True)
    except Exception as e:  # unknown model name, download failed, ...
        raise SeparationError(f"could not load Demucs model '{model}': {e}") from e

    def separate(path: Path) -> tuple[Stems, int]:
        try:
            _, stems = demucs.separate_audio_file(path)
        except Exception as e:
            raise SeparationError(f"could not separate {path.name}: {e}") from e
        return {name: t.T.cpu().numpy().astype(np.float32) for name, t in stems.items()}, int(
            demucs.samplerate
        )

    return separate


def _fingerprint(path: Path, model: str) -> dict[str, object]:
    st = path.stat()
    return {"input": path.name, "size": st.st_size, "mtime_ns": st.st_mtime_ns, "model": model}


def is_cached(input_path: Path, folder: Path, model: str) -> bool:
    """True if `folder` holds a finished separation of exactly this input file and model."""
    marker = folder / _MARKER
    try:
        return json.loads(marker.read_text(encoding="utf-8")) == _fingerprint(input_path, model)
    except (OSError, ValueError):
        return False


def separate(
    input_path: Path,
    folder: Path,
    model: str = DEFAULT_MODEL,
    *,
    log: Callable[[str], None] = print,
    load: Callable[[str], Separator] | None = None,
) -> None:
    """Split `input_path` into `<folder>/<stem>.flac`, unless that was already done.

    The result is reused as long as the input file and model stay the same, so trying
    another solo region does not separate the song again.
    """
    if is_cached(input_path, folder, model):
        log(f"  using separated stems from {folder}")
        return
    log(f"  separating {input_path.name} with Demucs '{model}' (this takes a while) ...")
    stems, sr = (load or load_separator)(model)(input_path)

    # Separated stems can peak slightly above full scale. Lower them all by the same amount
    # so they still add up to the original instead of clipping in the PCM file.
    peak = max((float(np.max(np.abs(a))) for a in stems.values() if a.size), default=0.0)
    gain = 0.99 / peak if peak > 0.99 else 1.0
    if gain < 1.0:
        log(f"  separated stems lowered by {-20 * np.log10(gain):.1f} dB to avoid clipping")

    folder.mkdir(parents=True, exist_ok=True)
    (folder / _MARKER).unlink(missing_ok=True)
    for old in folder.glob(f"*.{_EXT}"):
        old.unlink()
    for name, audio in stems.items():
        sf.write(folder / f"{name}.{_EXT}", audio * gain, sr, subtype="PCM_24")
    (folder / _MARKER).write_text(json.dumps(_fingerprint(input_path, model)), encoding="utf-8")
