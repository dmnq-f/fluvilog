"""Station reference data: the catalogue of WGMN stations.

Source of truth is constants.STATIONS, not the DB stations table — that table
exists only for the readings foreign key.
"""

import datetime as dt
from collections.abc import Iterable

from .constants import STATIONS
from .models import Station


def stations() -> list[Station]:
    """Return all WGMN stations sorted by code."""
    return sorted(STATIONS.values(), key=lambda s: s.code)


def started_after(codes: Iterable[str], start: dt.date) -> list[Station]:
    """Selected stations whose recording began strictly after `start`, by code.

    Backfilling a range that starts before a station existed yields no data for
    it in the early windows; callers use this to warn. `codes` must be valid
    station codes.
    """
    return sorted(
        (STATIONS[c] for c in codes if STATIONS[c].recording_since > start),
        key=lambda s: s.code,
    )


def recording_by(codes: Iterable[str], as_of: dt.date) -> list[str]:
    """Codes (in input order) whose station was already recording on `as_of`.

    A backfill window need not request stations whose recording began after the
    window — they have no data in it. `codes` must be valid station codes.
    """
    return [c for c in codes if STATIONS[c].recording_since <= as_of]
