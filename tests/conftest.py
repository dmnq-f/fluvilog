"""Shared fixtures: a temporary SQLite database seeded with known readings."""

import datetime as dt
from types import SimpleNamespace

import pandas as pd
import pytest

from fluvilog.storage import SqliteStorage

# Naive Europe/Berlin local time, matching how readings are stored.
BASE = dt.datetime(2026, 6, 1, 12, 0)


def _seed_frame() -> pd.DataFrame:
    """Build a fetch_history()-shaped frame with a deliberate trailing None."""
    ten = dt.timedelta(minutes=10)
    rows = [
        # code, station, water_body, parameter, unit, timestamp, value
        ("BL", "Blankenese", "Elbe", "Wassertemperatur", "°C", BASE, 18.1),
        ("BL", "Blankenese", "Elbe", "Wassertemperatur", "°C", BASE + ten, 18.3),
        ("BL", "Blankenese", "Elbe", "Wassertemperatur", "°C", BASE + 2 * ten, None),
        ("SH", "Seemannshöft", "Elbe", "Wassertemperatur", "°C", BASE, 17.5),
        ("BL", "Blankenese", "Elbe", "pH-Wert", "", BASE, 7.9),
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "code",
            "station",
            "water_body",
            "parameter",
            "unit",
            "timestamp",
            "value",
        ],
    )


@pytest.fixture
def seed(tmp_path: object) -> SimpleNamespace:
    """Write the seed frame to a fresh DB; expose its path and the base time."""
    path = str(tmp_path / "test.db")  # type: ignore[operator]
    fetched_at = dt.datetime(2026, 6, 1, 11, 0, tzinfo=dt.UTC)
    with SqliteStorage(path) as store:
        store.write(_seed_frame(), fetched_at)
    return SimpleNamespace(path=path, base=BASE)
