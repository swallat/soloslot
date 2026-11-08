"""Mute instruments in a solo section of a song or its stems to build play-along tracks."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("soloslot")
except PackageNotFoundError:  # pragma: no cover - running from a source tree without install
    __version__ = "0.0.0"

__all__ = ["__version__"]
