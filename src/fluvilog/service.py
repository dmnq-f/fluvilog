"""Continuous polling loop that persists WGMN readings to a Storage backend."""

import datetime as dt
import logging
import signal
import sqlite3
import threading
import time

import requests

from .constants import DEFAULT_MAX_CATCHUP_DAYS, MAX_LIST_WINDOW_DAYS
from .storage import Storage
from .wgmn import fetch_history


def _catchup_window(
    latest: dt.datetime | None, today: dt.date, cap_days: int
) -> tuple[dt.date, dt.date]:
    """Compute a poll's [date_from, today] window from the resume watermark.

    Resumes from the day of the latest stored reading so a gap back-fills, but
    reaches no further back than cap_days (a longer gap needs an explicit
    backfill). Always spans at least one day, since the source requires
    date_from < date_to. With no prior data, uses yesterday→today.
    """
    yesterday = today - dt.timedelta(days=1)
    if latest is None:
        return yesterday, today
    floor = today - dt.timedelta(days=cap_days)
    start = max(latest.date(), floor)
    return min(start, yesterday), today


def collect(
    station_codes: list[str],
    parameter_idx: list[int],
    storage: Storage,
    interval: float,
    *,
    max_catchup_days: int = DEFAULT_MAX_CATCHUP_DAYS,
    log: logging.Logger | None = None,
) -> int:
    """Poll the selected stations/parameters every `interval` seconds.

    Each poll resumes from the latest stored reading (the watermark), so an
    outage shorter than max_catchup_days back-fills automatically on the next
    poll; the catch-up window is capped at MAX_LIST_WINDOW_DAYS regardless, and a
    longer gap is logged with a pointer to `backfill`. Writes are idempotent, so
    the overlap each poll re-fetches is free. Network and storage errors in one
    iteration are logged and skipped; the loop continues. The interval is
    measured from each iteration's start, so a slow fetch shortens the following
    wait rather than accumulating drift. Runs until SIGINT or SIGTERM, returns 0.
    """
    log = log or logging.getLogger(__name__)
    cap_days = min(max_catchup_days, MAX_LIST_WINDOW_DAYS)
    stop = threading.Event()

    def _handle(signum: int, frame: object) -> None:
        log.info("received %s, shutting down", signal.Signals(signum).name)
        stop.set()

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)

    log.info(
        "collecting %d station(s) × %d parameter(s), every %.0fs",
        len(station_codes),
        len(parameter_idx),
        interval,
    )
    while not stop.is_set():
        started = time.monotonic()
        fetched_at = dt.datetime.now(dt.UTC)
        today = dt.date.today()
        try:
            latest = storage.latest_timestamp(station_codes=station_codes)
            gap_days = (today - latest.date()).days if latest is not None else 0
            if gap_days > cap_days:
                log.warning(
                    "last reading %s is %d days old, beyond the %d-day catch-up "
                    "cap; run `fluvilog backfill --from %s` to fill the gap",
                    latest.date(),  # pyright: ignore[reportOptionalMemberAccess]
                    gap_days,
                    cap_days,
                    latest.date().isoformat(),  # pyright: ignore[reportOptionalMemberAccess]
                )
            start, end = _catchup_window(latest, today, cap_days)
            df = fetch_history(station_codes, parameter_idx, start=start, end=end)
            inserted = storage.write(df, fetched_at)
            log.info("polled %s→%s, inserted %d new row(s)", start, end, inserted)
        except requests.RequestException as e:
            log.warning("fetch failed, skipping iteration: %s", e)
        except sqlite3.Error as e:
            log.warning("storage error, skipping iteration: %s", e)
        delay = max(0.0, interval - (time.monotonic() - started))
        log.info("next poll in %.0fs", delay)
        if stop.wait(timeout=delay):
            break
    return 0
