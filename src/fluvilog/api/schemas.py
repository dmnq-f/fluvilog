"""Public, validated HTTP response models.

Pydantic shapes for the wire contract, kept separate from models.py so the HTTP
surface can evolve independently of the internal domain models.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class HealthOut(BaseModel):
    """Liveness signal. status is always "ok"; reaching the handler is the check.

    Reports nothing about the database — the API is considered alive whenever it
    serves HTTP, independent of whether any readings have been written yet.
    version is the running fluvilog package version (build metadata, not state).
    """

    status: Literal["ok"] = "ok"
    version: str


class ReadyOut(BaseModel):
    """Readiness signal: whether the API can serve database-backed requests.

    service is always "ok" (the handler ran). db is a live read-only probe of
    the database: "ok" if it can be opened and queried, "unavailable" otherwise
    (e.g. before collect has created the file). The accompanying HTTP status is
    200 when db is "ok" and 503 when "unavailable".
    """

    service: Literal["ok"] = "ok"
    db: Literal["ok", "unavailable"]


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
