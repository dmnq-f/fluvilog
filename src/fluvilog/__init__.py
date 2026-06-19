"""fluvilog — near-real-time readings from Hamburg's water quality network (WGMN)."""

from importlib.metadata import PackageNotFoundError, version

from .wgmn import fetch, fetch_history

try:
    __version__ = version("fluvilog")
except PackageNotFoundError:  # pragma: no cover - source tree without install metadata
    __version__ = "0.0.0+unknown"

__all__ = ["__version__", "fetch", "fetch_history"]
