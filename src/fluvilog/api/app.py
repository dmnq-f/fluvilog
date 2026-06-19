"""FastAPI application factory for the optional HTTP read API.

Three GET endpoints over stored readings plus the station catalogue. Build with
create_app; the `fluvilog serve-api` subcommand runs it under uvicorn. Each
request gets its own read-only Storage, so reads never touch the poller's writer
connection or its schema.
"""

# Route handlers are registered by the @app.get decorators' side effect, which
# the type checker can't see; without this it flags them as unused.
# pyright: reportUnusedFunction=false

import sqlite3
from collections.abc import Iterator
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware

from .. import __version__, catalogue
from ..constants import BERLIN_TZ, MAX_WINDOW_DAYS, PARAMETERS, STATIONS
from ..storage import SqliteStorage
from .schemas import HealthOut, ReadingOut, ReadyOut, StationOut

_BERLIN = ZoneInfo(BERLIN_TZ)


def _as_berlin(value: datetime) -> datetime:
    """Make a query datetime tz-aware in Europe/Berlin (naive ⇒ interpreted as)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=_BERLIN)
    return value.astimezone(_BERLIN)


def _validate_filters(station: list[str] | None, parameter: list[str] | None) -> None:
    """Reject unknown station codes or parameter names with HTTP 422."""
    unknown_st = [s for s in station or [] if s not in STATIONS]
    if unknown_st:
        raise HTTPException(422, f"unknown station code(s): {unknown_st}")
    unknown_pa = [p for p in parameter or [] if p not in PARAMETERS]
    if unknown_pa:
        raise HTTPException(422, f"unknown parameter name(s): {unknown_pa}")


def _validate_window(start: datetime, end: datetime) -> None:
    """Reject reversed or over-wide windows with HTTP 422."""
    if start > end:
        raise HTTPException(422, "'from' must not be after 'to'")
    if end - start > timedelta(days=MAX_WINDOW_DAYS):
        raise HTTPException(422, f"window exceeds the {MAX_WINDOW_DAYS}-day limit")


def _db_reachable(db_path: str) -> bool:
    """Whether the database can be opened read-only and queried right now."""
    try:
        store = SqliteStorage.open_readonly(db_path)
    except sqlite3.Error:
        return False
    try:
        store.ping()
        return True
    except sqlite3.Error:
        return False
    finally:
        store.close()


def create_app(*, db_path: str, allowed_origins: list[str]) -> FastAPI:
    """Build the read-only FastAPI app bound to a SQLite database path.

    allowed_origins seeds CORS (GET only); an empty list permits no cross-origin
    request. db_path is opened read-only per request; the schema is never touched.
    """
    app = FastAPI(title="fluvilog API", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    def get_storage() -> Iterator[SqliteStorage]:
        store = SqliteStorage.open_readonly(db_path)
        try:
            yield store
        finally:
            store.close()

    @app.get("/api/health")
    def get_health() -> HealthOut:
        return HealthOut(version=__version__)

    @app.get("/api/ready")
    def get_ready(response: Response) -> ReadyOut:
        if _db_reachable(db_path):
            return ReadyOut(db="ok")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadyOut(db="unavailable")

    @app.get("/api/stations")
    def get_stations() -> list[StationOut]:
        return [StationOut(**asdict(s)) for s in catalogue.stations()]

    @app.get("/api/readings/latest")
    def get_latest(
        store: Annotated[SqliteStorage, Depends(get_storage)],
        station: Annotated[list[str] | None, Query()] = None,
        parameter: Annotated[list[str] | None, Query()] = None,
    ) -> list[ReadingOut]:
        _validate_filters(station, parameter)
        rows = store.latest_readings(station_codes=station, parameters=parameter)
        return [ReadingOut(**asdict(r)) for r in rows]

    @app.get("/api/readings")
    def get_readings(
        store: Annotated[SqliteStorage, Depends(get_storage)],
        start: Annotated[datetime, Query(alias="from")],
        end: Annotated[datetime | None, Query(alias="to")] = None,
        station: Annotated[list[str] | None, Query()] = None,
        parameter: Annotated[list[str] | None, Query()] = None,
    ) -> list[ReadingOut]:
        _validate_filters(station, parameter)
        start = _as_berlin(start)
        end = datetime.now(_BERLIN) if end is None else _as_berlin(end)
        _validate_window(start, end)
        rows = store.readings_in_window(
            start, end, station_codes=station, parameters=parameter
        )
        return [ReadingOut(**asdict(r)) for r in rows]

    return app
