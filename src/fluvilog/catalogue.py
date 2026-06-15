"""Station reference data: the catalogue of WGMN stations.

Source of truth is constants.STATIONS, not the DB stations table — that table
exists only for the readings foreign key.
"""

from .constants import STATIONS
from .models import Station


def stations() -> list[Station]:
    """Return all WGMN stations sorted by code."""
    return sorted(STATIONS.values(), key=lambda s: s.code)
