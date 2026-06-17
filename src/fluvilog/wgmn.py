"""Query the HamburgService water quality endpoint and parse its CSV responses."""

import datetime as dt
import logging
import threading
import time
from collections.abc import Callable, Iterable
from itertools import batched
from typing import Any
from urllib.parse import urljoin

import pandas as pd
import requests
from lxml.html import fromstring  # pyright: ignore[reportUnknownVariableType]

from .constants import (
    ENCODING,
    MAX_PARAMETERS,
    MAX_REQUESTS_PER_SECOND,
    MAX_STATIONS,
    PFX,
    REQUEST_BURST,
    START,
    STATIONS,
    TIMEOUT,
    USER_AGENT,
)

log = logging.getLogger(__name__)


class RateLimiter:
    """Thread-safe token-bucket rate limiter.

    The bucket holds up to `capacity` tokens and refills at `rate` tokens per
    second. acquire() consumes one token, blocking until one is available, so
    the sustained call rate is capped at `rate` while bursts up to `capacity`
    pass without delay.
    """

    def __init__(
        self,
        rate: float,
        capacity: float,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._rate = rate
        self._capacity = capacity
        self._tokens = capacity
        self._monotonic = monotonic
        self._sleep = sleep
        self._updated = monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Consume one token, blocking (via sleep) until one is available."""
        while True:
            with self._lock:
                now = self._monotonic()
                self._tokens = min(
                    self._capacity, self._tokens + (now - self._updated) * self._rate
                )
                self._updated = now
                # Tolerate float drift so an exactly-refilled token still counts.
                if self._tokens + 1e-9 >= 1.0:
                    self._tokens -= 1.0
                    return
                wait = (1.0 - self._tokens) / self._rate
            self._sleep(wait)


class _RateLimitedSession(requests.Session):
    """requests.Session that gates every send() through a shared RateLimiter.

    send() is the single funnel for all requests (including redirects), so the
    limiter bounds the whole HTTP surface regardless of caller.
    """

    def __init__(self, limiter: RateLimiter) -> None:
        super().__init__()
        self._limiter = limiter

    def send(
        self, request: requests.PreparedRequest, **kwargs: Any
    ) -> requests.Response:
        """Throttle, then delegate to the base implementation."""
        self._limiter.acquire()
        return super().send(request, **kwargs)


# Shared across every _fetch (and thus every backfill window), so the cap holds
# over the whole process, not per request batch.
_LIMITER = RateLimiter(MAX_REQUESTS_PER_SECOND, REQUEST_BURST)


def _ffill(cells: list[str]) -> list[str]:
    """Forward-fill empty cells with the last non-empty value.

    In the CSV the station short code appears only in the first column of each
    block; the following columns are empty and belong to the same station.
    """
    out: list[str] = []
    last = ""
    for cell in cells:
        cell = cell.strip()
        if cell:
            last = cell
        out.append(last)
    return out


def _station_index_map(session: requests.Session) -> dict[str, int]:
    """Map station code -> checkbox index, read from the live form.

    The form's station checkboxes are addressed by position
    (cblStationen:0..8) and their order is dictated upstream, not by us.
    Each box carries a label rendered as "{water_body} {station_name}",
    which is matched against STATIONS to recover the index for each code.
    Reading it per request follows a reordered form instead of silently
    mapping a code to the wrong checkbox.

    Raises RuntimeError if any known station's label is absent.
    """
    resp = session.get(START, timeout=TIMEOUT)
    doc = fromstring(resp.content)
    code_of = {f"{s.water_body} {s.name}": s.code for s in STATIONS.values()}

    found: dict[str, int] = {}
    for label in doc.findall(".//label"):
        for_id = label.get("for") or ""
        if "cblStationen_" not in for_id:
            continue
        code = code_of.get((label.text or "").strip())
        if code is not None:
            found[code] = int(for_id.rsplit("_", 1)[1])

    missing = sorted(set(STATIONS) - set(found))
    if missing:
        log.error("stations missing from form (renamed upstream?): %s", missing)
        raise RuntimeError(f"stations not found in form (renamed upstream?): {missing}")
    log.debug("mapped %d station(s) to form indices", len(found))
    return found


def _query(
    session: requests.Session,
    station_idx: Iterable[int],
    parameter_idx: Iterable[int],
    date_from: str,
    date_to: str,
) -> str:
    """Run a single query (<=5 stations, <=5 parameters).

    Returns the CSV text, or "" if the service returns no result.
    """
    resp = session.get(START, timeout=TIMEOUT)
    doc = fromstring(resp.content)
    inputs = doc.findall('.//input[@type="hidden"]')

    data: dict[str, str] = {
        name: (inp.get("value") or "") for inp in inputs if (name := inp.get("name"))
    }
    data["__EVENTTARGET"] = ""
    data["__EVENTARGUMENT"] = ""
    data[f"{PFX}txtVonDatum"] = date_from
    data[f"{PFX}txtBisDatum"] = date_to
    data[f"{PFX}btnAbfrage"] = "Anfrage"
    for i in station_idx:
        data[f"{PFX}cblStationen:{i}"] = "on"
    for j in parameter_idx:
        data[f"{PFX}clbMesswerte:{j}"] = "on"

    result_page = session.post(resp.url, data=data, timeout=TIMEOUT)
    result = fromstring(result_page.content)
    hrefs = [
        href
        for a in result.findall(".//a")
        if "hlDownload" in (a.get("id") or "") and (href := a.get("href"))
    ]
    if not hrefs:
        log.warning(
            "no download link in response (no data for %s..%s)", date_from, date_to
        )
        return ""
    csv = session.get(urljoin(result_page.url, hrefs[0]), timeout=TIMEOUT)
    csv.encoding = ENCODING
    return csv.text


def _parse(csv_text: str, *, latest_only: bool) -> pd.DataFrame:
    """Convert a CSV response to long format.

    The CSV is wide (timestamp + one column per station×parameter) at a
    10-minute cadence. With latest_only the last non-empty value per data
    column is kept, so sensors reporting at different times still contribute
    their most recent reading; otherwise every non-empty reading is emitted as
    its own row. Returns an empty frame when the CSV has no data rows.
    """
    rows = [line.split(";") for line in csv_text.splitlines() if line.strip()]
    if len(rows) < 7:
        log.warning("CSV had %d row(s), too few to parse", len(rows))
        return pd.DataFrame()

    codes = _ffill(rows[0])  # row 0: "Station Kurzname"
    parameters = rows[3]  # row 3: "Messgröße" (display name)
    units = rows[4]  # row 4: "Einheit"
    data_rows = rows[6:]

    records: list[dict[str, str]] = []
    for col in range(1, len(parameters)):
        parameter = parameters[col].strip()
        if not parameter:
            continue
        cells = [
            (row[0].strip(), row[col].strip())
            for row in data_rows
            if col < len(row) and row[col].strip()
        ]
        if not cells:
            continue
        if latest_only:
            cells = cells[-1:]
        for timestamp, value in cells:
            records.append(
                {
                    "code": codes[col].strip(),
                    "parameter": parameter,
                    "unit": units[col].strip() if col < len(units) else "",
                    "timestamp": timestamp,
                    "value": value,
                }
            )

    df = pd.DataFrame(records)
    if df.empty:
        return df
    df["value"] = pd.to_numeric(
        df["value"].str.replace(",", ".", regex=False), errors="coerce"
    )
    df["timestamp"] = pd.to_datetime(
        df["timestamp"], format="%d.%m.%Y %H:%M", errors="coerce"
    )
    log.debug("parsed %d reading(s) from CSV", len(df))
    return df


def _fetch(
    station_codes: list[str],
    parameter_idx: list[int],
    *,
    latest_only: bool,
    start: dt.date | None = None,
    end: dt.date | None = None,
) -> pd.DataFrame:
    """Query the selected stations/parameters and return a long-format frame.

    Splits the selection into blocks of <=5 (service limit). The date window is
    [start, end]; it defaults to yesterday→today. start/end must satisfy
    start <= end and span at most MAX_LIST_WINDOW_DAYS (a wider window degrades
    to daily means upstream) — neither is enforced here; callers pass valid
    bounds. With latest_only the result has one row per (code, parameter);
    otherwise one row per (code, parameter, timestamp).
    """
    end = end or dt.date.today()
    start = start or (end - dt.timedelta(days=1))
    date_from = start.strftime("%d.%m.%Y")
    date_to = end.strftime("%d.%m.%Y")

    session = _RateLimitedSession(_LIMITER)
    session.headers["User-Agent"] = USER_AGENT

    index_of = _station_index_map(session)
    station_idx = [index_of[c] for c in station_codes if c in index_of]

    blocks = [
        (sb, pb)
        for sb in batched(station_idx, MAX_STATIONS, strict=False)
        for pb in batched(parameter_idx, MAX_PARAMETERS, strict=False)
    ]
    log.debug("fetching %s..%s in %d block(s)", date_from, date_to, len(blocks))
    frames: list[pd.DataFrame] = []
    for n, (station_block, parameter_block) in enumerate(blocks, 1):
        log.info(
            "query %d/%d (%d stations × %d parameters, service is slow)",
            n,
            len(blocks),
            len(station_block),
            len(parameter_block),
        )
        frame = _parse(
            _query(session, station_block, parameter_block, date_from, date_to),
            latest_only=latest_only,
        )
        if not frame.empty:
            frames.append(frame)
    if not frames:
        log.warning("fetch returned no data for %s..%s", date_from, date_to)
        return pd.DataFrame()

    keys = ["code", "parameter"] if latest_only else ["code", "parameter", "timestamp"]
    df = pd.concat(frames, ignore_index=True)
    df = df.sort_values("timestamp").drop_duplicates(keys, keep="last")
    names = {s.code: s.name for s in STATIONS.values()}
    bodies = {s.code: s.water_body for s in STATIONS.values()}
    df["station"] = df["code"].map(names)
    df["water_body"] = df["code"].map(bodies)
    df = df[
        ["station", "water_body", "code", "parameter", "value", "unit", "timestamp"]
    ]
    return df.sort_values(["water_body", "station", "parameter"]).reset_index(drop=True)


def fetch(station_codes: list[str], parameter_idx: list[int]) -> pd.DataFrame:
    """Fetch the latest value for each selected station/parameter.

    One row per (code, parameter). See _fetch for the request strategy.
    """
    return _fetch(station_codes, parameter_idx, latest_only=True)


def fetch_history(
    station_codes: list[str],
    parameter_idx: list[int],
    *,
    start: dt.date | None = None,
    end: dt.date | None = None,
) -> pd.DataFrame:
    """Fetch every 10-min reading per station/parameter in the [start, end] window.

    Window defaults to yesterday→today; see _fetch for the bound constraints.
    Same columns as fetch, but one row per (code, parameter, timestamp).
    """
    return _fetch(station_codes, parameter_idx, latest_only=False, start=start, end=end)
