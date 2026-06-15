"""Catalogue: all 9 stations, sorted, with coordinates inside the Hamburg box."""

import datetime as dt

from fluvilog.catalogue import recording_by, started_after, stations

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


def test_started_after_flags_stations_newer_than_date() -> None:
    all_codes = [s.code for s in stations()]
    flagged = [s.code for s in started_after(all_codes, dt.date(1990, 1, 1))]
    assert flagged == ["BK", "FH", "HA", "LB", "TA", "WA"]  # post-1990, code-sorted


def test_started_after_is_strict_and_respects_selection() -> None:
    # The Elbe trio began exactly 1988-05-01; that day is not "after".
    assert started_after(["BU", "SH", "BL"], dt.date(1988, 5, 1)) == []
    # Selection is honoured: only FH is newer than 1990 here, not BL.
    assert [s.code for s in started_after(["BL", "FH"], dt.date(1990, 1, 1))] == ["FH"]
    # Everything predates 2000, so nothing is flagged.
    assert started_after([s.code for s in stations()], dt.date(2000, 1, 1)) == []


def test_recording_by_keeps_active_stations_in_input_order() -> None:
    all_codes = [s.code for s in stations()]  # code-sorted
    # Only the three 1988 Elbe stations were recording by 1990 (input order kept).
    assert recording_by(all_codes, dt.date(1990, 1, 1)) == ["BL", "BU", "SH"]
    # Order follows the input, not the catalogue: WA before BU here.
    assert recording_by(["WA", "BU"], dt.date(2000, 1, 1)) == ["WA", "BU"]


def test_recording_by_boundary_and_empty() -> None:
    # recording_since == as_of counts as recording (data exists that day).
    assert recording_by(["BL"], dt.date(1988, 5, 1)) == ["BL"]
    # The day before any station existed yields nothing.
    assert recording_by([s.code for s in stations()], dt.date(1988, 4, 30)) == []
