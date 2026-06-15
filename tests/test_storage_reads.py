"""Storage read surface: latest_readings, readings_in_window, open_readonly."""

import datetime as dt
import sqlite3
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from fluvilog.storage import SqliteStorage

BERLIN = ZoneInfo("Europe/Berlin")
TEN = dt.timedelta(minutes=10)


def test_latest_one_row_per_pair(seed: SimpleNamespace) -> None:
    store = SqliteStorage.open_readonly(seed.path)
    try:
        rows = store.latest_readings()
    finally:
        store.close()
    keys = [(r.station_code, r.parameter) for r in rows]
    assert len(keys) == len(set(keys))
    assert set(keys) == {
        ("BL", "Wassertemperatur"),
        ("SH", "Wassertemperatur"),
        ("BL", "pH-Wert"),
    }


def test_latest_returns_stored_none_and_aware_ts(seed: SimpleNamespace) -> None:
    store = SqliteStorage.open_readonly(seed.path)
    try:
        by_key = {(r.station_code, r.parameter): r for r in store.latest_readings()}
    finally:
        store.close()
    latest = by_key[("BL", "Wassertemperatur")]
    assert latest.value is None  # latest stored row wins, even when None
    assert latest.timestamp == (seed.base + 2 * TEN).replace(tzinfo=BERLIN)
    assert all(r.timestamp.tzinfo == BERLIN for r in by_key.values())


def test_latest_filters(seed: SimpleNamespace) -> None:
    store = SqliteStorage.open_readonly(seed.path)
    try:
        only_bl = store.latest_readings(station_codes=["BL"])
        only_ph = store.latest_readings(parameters=["pH-Wert"])
        combined = store.latest_readings(
            station_codes=["BL"], parameters=["Wassertemperatur"]
        )
        missing = store.latest_readings(station_codes=["BU"])
    finally:
        store.close()
    assert {(r.station_code, r.parameter) for r in only_bl} == {
        ("BL", "Wassertemperatur"),
        ("BL", "pH-Wert"),
    }
    assert {r.parameter for r in only_ph} == {"pH-Wert"}
    assert [(r.station_code, r.parameter) for r in combined] == [
        ("BL", "Wassertemperatur")
    ]
    assert missing == []


def test_window_inclusive_and_filters(seed: SimpleNamespace) -> None:
    base = seed.base
    store = SqliteStorage.open_readonly(seed.path)
    try:
        at_base = store.readings_in_window(base, base)
        full = store.readings_in_window(base, base + 2 * TEN)
        aware = store.readings_in_window(
            base.replace(tzinfo=BERLIN), base.replace(tzinfo=BERLIN)
        )
        filtered = store.readings_in_window(
            base, base + 2 * TEN, station_codes=["BL"], parameters=["Wassertemperatur"]
        )
        empty = store.readings_in_window(
            base + dt.timedelta(days=1), base + dt.timedelta(days=2)
        )
    finally:
        store.close()
    assert {(r.station_code, r.parameter) for r in at_base} == {
        ("BL", "Wassertemperatur"),
        ("SH", "Wassertemperatur"),
        ("BL", "pH-Wert"),
    }
    assert len(full) == 5  # both ends inclusive, all seeded rows
    assert len(aware) == 3  # naive and aware bounds behave the same
    assert {(r.station_code, r.parameter) for r in filtered} == {
        ("BL", "Wassertemperatur")
    }
    assert empty == []


def test_latest_timestamp_is_global_max_and_aware(seed: SimpleNamespace) -> None:
    store = SqliteStorage.open_readonly(seed.path)
    try:
        overall = store.latest_timestamp()
        only_sh = store.latest_timestamp(station_codes=["SH"])
        missing = store.latest_timestamp(station_codes=["BU"])
    finally:
        store.close()
    # Greatest stored timestamp wins even though that row's value is None.
    assert overall == (seed.base + 2 * TEN).replace(tzinfo=BERLIN)
    assert only_sh == seed.base.replace(tzinfo=BERLIN)  # SH has only the base row
    assert missing is None  # no rows match -> None, never raises


def test_open_readonly_rejects_writes(seed: SimpleNamespace) -> None:
    store = SqliteStorage.open_readonly(seed.path)
    try:
        assert store.latest_readings()  # reads work on the existing schema
        with pytest.raises(sqlite3.OperationalError):
            store.init_schema()  # writing/seeding fails — connection is read-only
    finally:
        store.close()


def test_open_readonly_missing_file(tmp_path: object) -> None:
    with pytest.raises(sqlite3.OperationalError):
        SqliteStorage.open_readonly(str(tmp_path / "nope.db"))  # type: ignore[operator]
