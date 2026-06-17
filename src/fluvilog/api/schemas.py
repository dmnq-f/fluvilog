"""Public, validated HTTP response models.

Pydantic shapes for the wire contract, kept separate from models.py so the HTTP
surface can evolve independently of the internal domain models.
"""

from datetime import date, datetime

from pydantic import BaseModel


class StationOut(BaseModel):
    """A station in the catalogue.

    latitude/longitude are WGS84 degrees. recording_since is the date the
    station began reporting, serialised as ISO 8601 (YYYY-MM-DD).
    """

    code: str
    name: str
    water_body: str
    latitude: float
    longitude: float
    recording_since: date


class ReadingOut(BaseModel):
    """A single reading. timestamp serialises as ISO 8601 with offset."""

    station_code: str
    parameter: str
    unit: str
    timestamp: datetime
    value: float | None
