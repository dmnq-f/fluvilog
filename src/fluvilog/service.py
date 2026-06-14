"""Continuous polling loop that persists WGMN readings to a Storage backend."""

import datetime as dt
import logging
import signal
import sqlite3
import threading
import time

import requests

from .constants import MIN_INTERVAL
from .storage import Storage
from .wgmn import fetch_history

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


def serve(
    station_codes: list[str],
    parameter_idx: list[int],
    storage: Storage,
    interval: float,
    *,
    log: logging.Logger | None = None,
) -> int:
    """Poll the selected stations/parameters every `interval` seconds.

    Each poll fetches the full window and persists it idempotently. Network and
    storage errors in one iteration are logged and skipped; the loop continues.
    The interval is measured from each iteration's start, so a slow fetch
    shortens the following wait rather than accumulating drift. Runs until
    SIGINT or SIGTERM, then returns 0.
    """
    log = log or logging.getLogger(__name__)
    stop = threading.Event()

    def _handle(signum: int, frame: object) -> None:
        log.info("received %s, shutting down", signal.Signals(signum).name)
        stop.set()

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)

    log.info(
        "serving %d station(s) × %d parameter(s), every %.0fs",
        len(station_codes),
        len(parameter_idx),
        interval,
    )
    while not stop.is_set():
        started = time.monotonic()
        fetched_at = dt.datetime.now(dt.UTC)
        try:
            df = fetch_history(station_codes, parameter_idx)
            inserted = storage.write(df, fetched_at)
            log.info("inserted %d new row(s)", inserted)
        except requests.RequestException as e:
            log.warning("fetch failed, skipping iteration: %s", e)
        except sqlite3.Error as e:
            log.warning("storage error, skipping iteration: %s", e)
        delay = max(0.0, interval - (time.monotonic() - started))
        log.info("next poll in %.0fs", delay)
        if stop.wait(timeout=delay):
            break
    return 0
