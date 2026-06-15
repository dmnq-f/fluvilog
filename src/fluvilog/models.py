"""Domain dataclasses shared across the package.

Plain dataclasses, deliberately not Pydantic, so the persistence and read
layers carry no dependency on the optional API tier. See fluvilog.api.schemas
for the public HTTP shapes.
"""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class Station:
    """A WGMN station and its static reference data.

    latitude/longitude are decimal degrees (EPSG:4326). recording_since is the
    date the station began reporting — the earliest day a backfill can reach.
    """

    code: str
    name: str
    water_body: str
    latitude: float
    longitude: float
    recording_since: date


@dataclass(frozen=True, slots=True)
class ReadingRecord:
    """A single stored reading.

    parameter is the display name (e.g. "Wassertemperatur"). timestamp is
    tz-aware Europe/Berlin. value is None when the sensor reported no value;
    None is preserved, not dropped.
    """

    station_code: str
    parameter: str
    unit: str
    timestamp: datetime
    value: float | None
