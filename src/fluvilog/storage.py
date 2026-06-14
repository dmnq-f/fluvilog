"""Persistence backends for water-quality readings.

Defines the Storage interface and a stdlib-sqlite3 implementation. Other SQL
backends can be added by implementing Storage without touching the serve loop.
"""

import abc
import datetime as dt
import os
import sqlite3
from itertools import repeat

import pandas as pd

from .constants import (
    PARAMETERS,
    STATIONS,
    TABLE_PARAMETERS,
    TABLE_READINGS,
    TABLE_STATIONS,
    VIEW_READINGS_FULL,
)


class IncompatibleSchemaError(Exception):
    """A database file holds a schema this version cannot use."""


# Bumped on any breaking change to the schema below; stored in the file's
# PRAGMA user_version.
SCHEMA_VERSION = 1

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {TABLE_STATIONS} (
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    water_body  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS {TABLE_PARAMETERS} (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE,
    unit  TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS {TABLE_READINGS} (
    station_code  TEXT    NOT NULL REFERENCES {TABLE_STATIONS}(code),
    parameter_id  INTEGER NOT NULL REFERENCES {TABLE_PARAMETERS}(id),
    timestamp     TEXT    NOT NULL,
    value         REAL,
    fetched_at    TEXT    NOT NULL,
    PRIMARY KEY (station_code, parameter_id, timestamp)
);
CREATE VIEW IF NOT EXISTS {VIEW_READINGS_FULL} AS
SELECT s.code AS code, s.name AS station, s.water_body AS water_body,
       p.name AS parameter, p.unit AS unit,
       r.timestamp AS timestamp, r.value AS value, r.fetched_at AS fetched_at
FROM {TABLE_READINGS} r
JOIN {TABLE_STATIONS} s ON s.code = r.station_code
JOIN {TABLE_PARAMETERS} p ON p.id = r.parameter_id;
"""

_SEED_STATIONS = (
    f"INSERT OR IGNORE INTO {TABLE_STATIONS} (code, name, water_body) VALUES (?, ?, ?)"
)
_SEED_PARAMETERS = f"INSERT OR IGNORE INTO {TABLE_PARAMETERS} (id, name) VALUES (?, ?)"
_INSERT_PARAMETER = f"INSERT INTO {TABLE_PARAMETERS} (name) VALUES (?)"
_UPDATE_UNIT = f"UPDATE {TABLE_PARAMETERS} SET unit = ? WHERE id = ?"

_INSERT = (
    f"INSERT OR IGNORE INTO {TABLE_READINGS} "
    "(station_code, parameter_id, timestamp, value, fetched_at) "
    "VALUES (?, ?, ?, ?, ?)"
)

_ISO = "%Y-%m-%dT%H:%M:%S"


class Storage(abc.ABC):
    """Backend that persists readings keyed by (code, parameter, timestamp).

    Implementations are not required to be thread-safe; the serve loop uses one
    instance from a single thread. Usable as a context manager: __enter__ calls
    init_schema, __exit__ calls close.
    """

    @abc.abstractmethod
    def init_schema(self) -> None:
        """Create tables/indexes if absent. Idempotent."""

    @abc.abstractmethod
    def write(self, df: pd.DataFrame, fetched_at: dt.datetime) -> int:
        """Insert readings idempotently; return the count of new rows.

        df has fetch_history() columns. Rows whose (code, parameter, timestamp)
        already exist are skipped; rows with a missing timestamp are dropped.
        """

    @abc.abstractmethod
    def close(self) -> None:
        """Release the underlying connection."""

    def __enter__(self) -> "Storage":
        self.init_schema()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


class SqliteStorage(Storage):
    """SQLite-backed storage on a normalized star schema.

    A `readings` fact table references `stations` (by code) and `parameters`
    (by surrogate id); a `readings_full` view rejoins them into the wide,
    denormalized shape for ad-hoc queries. Station/parameter dimensions are
    seeded from the catalogues in constants; parameter units are learned from
    written data. Reading timestamps are stored as naive local
    (Europe/Berlin) ISO 8601; fetched_at is UTC.

    Single-writer: do not run two serve processes against one database file.
    WAL is enabled so a concurrent reader never blocks the writer.

    The schema is tracked by PRAGMA user_version; init_schema raises
    IncompatibleSchemaError if a file's version is unsupported by this build.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = os.fspath(path)
        self._conn = sqlite3.connect(self._path)
        self._param_ids: dict[str, int] | None = None

    def init_schema(self) -> None:
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._check_version()

        self._conn.executescript(_SCHEMA)
        self._conn.executemany(
            _SEED_STATIONS,
            [(code, name, body) for code, (name, body) in STATIONS.items()],
        )
        self._conn.executemany(_SEED_PARAMETERS, list(enumerate(PARAMETERS)))
        self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self._conn.commit()

    def _check_version(self) -> None:
        """Validate the file's schema version. Raises IncompatibleSchemaError.

        A matching version, or a brand-new empty file (which init_schema then
        stamps), is accepted. A populated file at version 0 predates versioning;
        any other version is unsupported by this build.
        """
        version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if version == SCHEMA_VERSION:
            return
        if version == 0:
            tables = self._conn.execute(
                "SELECT count(*) FROM sqlite_master WHERE type = 'table'"
            ).fetchone()[0]
            if tables == 0:
                return
            raise IncompatibleSchemaError(
                f"{self._path!r} predates schema versioning; remove the file "
                "(or pass a new --db path) to recreate it."
            )
        raise IncompatibleSchemaError(
            f"{self._path!r} has schema version {version}, unsupported by this "
            f"build (expected {SCHEMA_VERSION})."
        )

    def _parameter_ids(self) -> dict[str, int]:
        """Cache and return the parameter name -> id map from the catalogue."""
        if self._param_ids is None:
            self._param_ids = {
                name: pid
                for pid, name in self._conn.execute(
                    f"SELECT id, name FROM {TABLE_PARAMETERS}"
                )
            }
        return self._param_ids

    def write(self, df: pd.DataFrame, fetched_at: dt.datetime) -> int:
        if df.empty:
            return 0
        df = df[df["timestamp"].notna()]
        if df.empty:
            return 0

        ids = self._parameter_ids()
        for name in df["parameter"].unique():
            if name not in ids:
                cursor = self._conn.execute(_INSERT_PARAMETER, (name,))
                ids[name] = int(cursor.lastrowid or 0)

        units = df[["parameter", "unit"]].drop_duplicates("parameter")
        self._conn.executemany(
            _UPDATE_UNIT,
            [(unit, ids[name]) for name, unit in units.itertuples(index=False)],
        )

        timestamps = df["timestamp"].dt.strftime(_ISO)
        values = df["value"].astype(object).where(df["value"].notna(), None)
        fetched = fetched_at.strftime(_ISO)
        rows = list(
            zip(
                df["code"],
                [ids[name] for name in df["parameter"]],
                timestamps,
                values,
                repeat(fetched),
            )
        )

        before = self._conn.total_changes
        self._conn.executemany(_INSERT, rows)
        self._conn.commit()
        return self._conn.total_changes - before

    def close(self) -> None:
        self._conn.close()
