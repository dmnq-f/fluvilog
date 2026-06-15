"""Catalogue: all 9 stations, sorted, with coordinates inside the Hamburg box."""

import datetime as dt

from fluvilog.catalogue import stations

# Hamburg bounding box (acceptance §8): rejects placeholders and lat/lon swaps.
LAT_MIN, LAT_MAX = 53.35, 53.75
LON_MIN, LON_MAX = 9.65, 10.35


def test_nine_stations_sorted_by_code() -> None:
    codes = [s.code for s in stations()]
    assert len(codes) == 9
    assert codes == sorted(codes)


def test_coordinates_within_hamburg_box() -> None:
    for s in stations():
        assert LAT_MIN <= s.latitude <= LAT_MAX, s
        assert LON_MIN <= s.longitude <= LON_MAX, s


def test_recording_since_present_and_plausible() -> None:
    by_code = {s.code: s.recording_since for s in stations()}
    assert by_code["BL"] == dt.date(1988, 5, 1)  # earliest Elbe stations
    for code, since in by_code.items():
        # WGMN began in 1988; nothing predates it, nothing is in the future.
        assert dt.date(1988, 1, 1) <= since <= dt.date.today(), code
