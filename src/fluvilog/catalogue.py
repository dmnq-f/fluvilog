"""Station reference data: the catalogue joining names with coordinates.

Source of truth is constants (STATIONS + STATION_COORDS), not the DB stations
table — that table exists only for the readings foreign key.
"""

from .constants import STATION_COORDS, STATIONS
from .records import StationRecord


def _check_coords() -> None:
    """Raise ValueError if any STATIONS code lacks a STATION_COORDS entry."""
    missing = set(STATIONS) - set(STATION_COORDS)
    if missing:
        raise ValueError(
            f"STATION_COORDS is missing coordinates for: {sorted(missing)}"
        )


_check_coords()


def stations() -> list[StationRecord]:
    """Return all WGMN stations sorted by code, each with WGS84 coordinates."""
    return [
        StationRecord(
            code=code,
            name=name,
            water_body=water_body,
            latitude=STATION_COORDS[code][0],
            longitude=STATION_COORDS[code][1],
        )
        for code, (name, water_body) in sorted(STATIONS.items())
    ]
