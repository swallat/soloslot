"""Clear a solo section out of stem WAVs to build play-along backing tracks."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("stem-solo-gap")
except PackageNotFoundError:  # pragma: no cover - running from a source tree without install
    __version__ = "0.0.0"

__all__ = ["__version__"]
