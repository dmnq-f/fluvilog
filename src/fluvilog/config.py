"""Environment-variable configuration layer.

Resolves runtime defaults from FLUVILOG_* environment variables, falling back to
the built-in defaults in `constants`. The resolved values feed argparse as
defaults, so an explicit command-line flag overrides the environment, which in
turn overrides the built-in default.

This is the seam where a future file-based configuration layer would slot in:
read a file, let the environment override it, then the command line over that.
"""

import logging
import os
from dataclasses import dataclass

from .constants import (
    DEFAULT_API_HOST,
    DEFAULT_API_PORT,
    DEFAULT_DB_PATH,
    DEFAULT_INTERVAL,
    DEFAULT_LOG_LEVEL,
    DEFAULT_MAX_CATCHUP_DAYS,
    MIN_INTERVAL,
)

ENV_PREFIX = "FLUVILOG_"
_UNITS = {"s": 1, "m": 60, "h": 3600}


def parse_interval(text: str) -> float:
    """Parse '600', '30s', '10m', or '1h' to seconds.

    A bare number is seconds; a trailing s/m/h scales accordingly. The result
    must be at least MIN_INTERVAL. Raises ValueError on malformed or too-small
    input.
    """
    text = text.strip().lower()
    if text and text[-1] in _UNITS:
        seconds = float(text[:-1]) * _UNITS[text[-1]]
    else:
        seconds = float(text)
    if seconds < MIN_INTERVAL:
        raise ValueError(f"interval must be >= {MIN_INTERVAL}s")
    return seconds


def parse_log_level(text: str) -> int:
    """Map a level name (case-insensitive) to its logging integer.

    Accepts DEBUG/INFO/WARNING/ERROR/CRITICAL. Raises ValueError on an unknown
    name.
    """
    level = logging.getLevelNamesMapping().get(text.strip().upper())
    if level is None:
        raise ValueError(f"unknown log level: {text!r}")
    return level


@dataclass(frozen=True, slots=True)
class EnvConfig:
    """Configuration defaults resolved from the environment.

    Coerced fields (`interval`, `api_port`, `log_level`) are kept as strings so
    the owning argument's `type=` performs coercion and error reporting, exactly
    as for a value typed on the command line. List fields are split on commas;
    `stations` is None when unset, meaning "all stations".
    """

    db: str
    interval: str
    max_catchup: str
    stations: list[str] | None
    api_host: str
    api_port: str
    cors_origins: list[str]
    log_level: str


def _get(name: str) -> str | None:
    """Return the stripped value of FLUVILOG_<name>, or None if unset or blank."""
    raw = os.environ.get(ENV_PREFIX + name)
    if raw is None:
        return None
    raw = raw.strip()
    return raw or None


def _split(raw: str | None) -> list[str]:
    """Split a comma-separated environment value into trimmed, non-empty items."""
    if raw is None:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def load() -> EnvConfig:
    """Resolve configuration defaults from the FLUVILOG_* environment variables.

    Reads the process environment at call time; unset or blank variables fall
    back to the built-in defaults in `constants`.
    """
    return EnvConfig(
        db=_get("DB") or DEFAULT_DB_PATH,
        interval=_get("INTERVAL") or str(DEFAULT_INTERVAL),
        max_catchup=_get("MAX_CATCHUP") or str(DEFAULT_MAX_CATCHUP_DAYS),
        stations=_split(_get("STATION")) or None,
        api_host=_get("API_HOST") or DEFAULT_API_HOST,
        api_port=_get("API_PORT") or str(DEFAULT_API_PORT),
        cors_origins=_split(_get("CORS_ORIGIN")),
        log_level=_get("LOG_LEVEL") or DEFAULT_LOG_LEVEL,
    )
