"""Catalogue: all 9 stations, sorted, with coordinates inside the Hamburg box."""

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
