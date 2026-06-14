"""Public, validated HTTP response models.

Pydantic shapes for the wire contract, kept separate from records.py so the HTTP
surface can evolve independently of the internal storage records.
"""

from datetime import datetime

from pydantic import BaseModel


class StationOut(BaseModel):
    """A station in the catalogue. latitude/longitude are WGS84 degrees."""

    code: str
    name: str
    water_body: str
    latitude: float
    longitude: float


class ReadingOut(BaseModel):
    """A single reading. timestamp serialises as ISO 8601 with offset."""

    station_code: str
    parameter: str
    unit: str
    timestamp: datetime
    value: float | None
