"""fluvilog — near-real-time readings from Hamburg's water quality network (WGMN)."""

from .wgmn import fetch, fetch_history

__all__ = ["fetch", "fetch_history"]
