"""Continuous polling loop that persists WGMN readings to a Storage backend."""

import datetime as dt
import logging
import signal
import sqlite3
import threading
import time
from collections.abc import Iterator

import requests

from .constants import (
    BACKFILL_CHUNK_DAYS,
    DEFAULT_MAX_CATCHUP_DAYS,
    MAX_LIST_WINDOW_DAYS,
)
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


def _date_chunks(
    start: dt.date, end: dt.date, chunk_days: int
) -> Iterator[tuple[dt.date, dt.date]]:
    """Yield [from, to] windows tiling [start, end], each at most chunk_days wide.

    Assumes start < end. Consecutive windows share a boundary day; idempotent
    writes make that overlap harmless and guarantee no missing day.
    """
    step = dt.timedelta(days=chunk_days)
    cur = start
    while cur < end:
        nxt = min(cur + step, end)
        yield cur, nxt
        cur = nxt


def backfill(
    station_codes: list[str],
    parameter_idx: list[int],
    storage: Storage,
    start: dt.date,
    end: dt.date,
    *,
    chunk_days: int = BACKFILL_CHUNK_DAYS,
    log: logging.Logger | None = None,
) -> int:
    """Fetch and store every 10-min reading in [start, end] (inclusive dates).

    The range is split into windows of at most chunk_days, because the source
    serves 10-min values only for spans up to MAX_LIST_WINDOW_DAYS (wider windows
    degrade to daily means). Each window is fetched and written idempotently, so
    a re-run fills only what is missing and a failed window can be retried. A
    single-day range is widened by a day, since the source needs date_from <
    date_to. Per-window network/storage errors are logged and skipped;
    SIGINT/SIGTERM stops cleanly after the current window. Returns 0.
    """
    log = log or logging.getLogger(__name__)
    stop = threading.Event()

    def _handle(signum: int, frame: object) -> None:
        log.info("received %s, stopping after this window", signal.Signals(signum).name)
        stop.set()

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)

    if start == end:
        end = end + dt.timedelta(days=1)
    windows = list(_date_chunks(start, end, min(chunk_days, MAX_LIST_WINDOW_DAYS - 1)))
    log.info(
        "backfilling %d station(s) × %d parameter(s), %s→%s in %d window(s)",
        len(station_codes),
        len(parameter_idx),
        start,
        end,
        len(windows),
    )
    total = 0
    for n, (win_start, win_end) in enumerate(windows, 1):
        if stop.is_set():
            break
        fetched_at = dt.datetime.now(dt.UTC)
        try:
            df = fetch_history(
                station_codes, parameter_idx, start=win_start, end=win_end
            )
            inserted = storage.write(df, fetched_at)
            total += inserted
            log.info(
                "window %d/%d %s→%s: inserted %d new row(s)",
                n,
                len(windows),
                win_start,
                win_end,
                inserted,
            )
        except requests.RequestException as e:
            log.warning("window %d/%d fetch failed, skipping: %s", n, len(windows), e)
        except sqlite3.Error as e:
            log.warning("window %d/%d storage error, skipping: %s", n, len(windows), e)
    log.info("backfill complete: %d new row(s) total", total)
    return 0
