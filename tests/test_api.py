"""HTTP API: endpoints, filters, validation (§7), and ISO-offset timestamps."""

import datetime as dt
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from fluvilog.api import create_app  # noqa: E402

TEN = dt.timedelta(minutes=10)


@pytest.fixture
def client(seed: SimpleNamespace) -> TestClient:
    app = create_app(db_path=seed.path, allowed_origins=["http://localhost:5173"])
    return TestClient(app)


def test_health(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready_db_reachable(client: TestClient) -> None:
    resp = client.get("/api/ready")
    assert resp.status_code == 200
    assert resp.json() == {"service": "ok", "db": "ok"}


def test_ready_db_unavailable(tmp_path: object) -> None:
    missing = str(tmp_path / "absent.db")  # type: ignore[operator]
    app = create_app(db_path=missing, allowed_origins=[])
    resp = TestClient(app).get("/api/ready")
    assert resp.status_code == 503
    assert resp.json() == {"service": "ok", "db": "unavailable"}


def test_stations(client: TestClient) -> None:
    resp = client.get("/api/stations")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 9
    assert all({"latitude", "longitude", "recording_since"} <= set(s) for s in data)


def test_latest_one_per_pair(client: TestClient) -> None:
    resp = client.get("/api/readings/latest")
    assert resp.status_code == 200
    keys = [(r["station_code"], r["parameter"]) for r in resp.json()]
    assert len(keys) == len(set(keys))


def test_timestamps_carry_offset(client: TestClient) -> None:
    rows = client.get("/api/readings/latest").json()
    assert rows
    for r in rows:
        ts = r["timestamp"]
        assert ts[-6] in "+-" and ts[-3] == ":"  # e.g. ...+02:00


def test_window_filters_and_inclusive(
    client: TestClient, seed: SimpleNamespace
) -> None:
    frm = seed.base.isoformat()
    to = (seed.base + 2 * TEN).isoformat()
    resp = client.get("/api/readings", params={"from": frm, "to": to})
    assert resp.status_code == 200
    assert len(resp.json()) == 5
    narrowed = client.get(
        "/api/readings",
        params={
            "from": frm,
            "to": to,
            "station": "BL",
            "parameter": "Wassertemperatur",
        },
    )
    assert {(r["station_code"], r["parameter"]) for r in narrowed.json()} == {
        ("BL", "Wassertemperatur")
    }


def test_empty_window_is_200_empty(client: TestClient, seed: SimpleNamespace) -> None:
    frm = (seed.base + dt.timedelta(days=5)).isoformat()
    to = (seed.base + dt.timedelta(days=6)).isoformat()
    resp = client.get("/api/readings", params={"from": frm, "to": to})
    assert resp.status_code == 200
    assert resp.json() == []


def test_unknown_station_is_422(client: TestClient) -> None:
    assert (
        client.get("/api/readings/latest", params={"station": "ZZ"}).status_code == 422
    )


def test_unknown_parameter_is_422(client: TestClient) -> None:
    resp = client.get("/api/readings/latest", params={"parameter": "Nonsense"})
    assert resp.status_code == 422


def test_from_after_to_is_422(client: TestClient, seed: SimpleNamespace) -> None:
    frm = seed.base.isoformat()
    to = (seed.base - dt.timedelta(days=1)).isoformat()
    assert (
        client.get("/api/readings", params={"from": frm, "to": to}).status_code == 422
    )


def test_window_too_wide_is_422(client: TestClient, seed: SimpleNamespace) -> None:
    frm = seed.base.isoformat()
    to = (seed.base + dt.timedelta(days=60)).isoformat()
    assert (
        client.get("/api/readings", params={"from": frm, "to": to}).status_code == 422
    )


def test_missing_from_is_422(client: TestClient) -> None:
    assert client.get("/api/readings").status_code == 422
