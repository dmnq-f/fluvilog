"""Collect/backfill helpers: catch-up window and date chunking."""

import datetime as dt
from zoneinfo import ZoneInfo

from fluvilog.service import _catchup_window, _date_chunks

BERLIN = ZoneInfo("Europe/Berlin")
TODAY = dt.date(2026, 6, 15)
JAN1 = dt.date(2025, 1, 1)


def _ts(d: dt.date) -> dt.datetime:
    """A tz-aware Berlin watermark at noon on the given date."""
    return dt.datetime(d.year, d.month, d.day, 12, 0, tzinfo=BERLIN)


def test_no_prior_data_uses_yesterday_to_today() -> None:
    assert _catchup_window(None, TODAY, cap_days=7) == (
        TODAY - dt.timedelta(days=1),
        TODAY,
    )


def test_recent_watermark_resumes_from_its_day() -> None:
    latest = _ts(TODAY - dt.timedelta(days=3))
    assert _catchup_window(latest, TODAY, cap_days=7) == (latest.date(), TODAY)


def test_gap_beyond_cap_is_clamped_to_cap() -> None:
    latest = _ts(TODAY - dt.timedelta(days=30))
    assert _catchup_window(latest, TODAY, cap_days=7) == (
        TODAY - dt.timedelta(days=7),
        TODAY,
    )


def test_caught_up_today_polls_single_day() -> None:
    # The source accepts equal from/to bounds, so a same-day watermark polls today only.
    assert _catchup_window(_ts(TODAY), TODAY, cap_days=7) == (TODAY, TODAY)


def _days(n: int) -> dt.timedelta:
    return dt.timedelta(days=n)


def test_chunks_single_window_when_range_fits() -> None:
    assert list(_date_chunks(JAN1, JAN1 + _days(5), 7)) == [(JAN1, JAN1 + _days(5))]


def test_chunks_exact_multiple_tile_contiguously() -> None:
    out = list(_date_chunks(JAN1, JAN1 + _days(14), 7))
    assert out == [
        (JAN1, JAN1 + _days(7)),
        (JAN1 + _days(7), JAN1 + _days(14)),
    ]


def test_chunks_cover_range_with_partial_tail() -> None:
    out = list(_date_chunks(JAN1, JAN1 + _days(20), 7))
    # Every window is <= 7 days, contiguous, and spans exactly [start, end].
    assert all(b - a <= _days(7) for a, b in out)
    assert out[0][0] == JAN1 and out[-1][1] == JAN1 + _days(20)
    assert all(out[i][1] == out[i + 1][0] for i in range(len(out) - 1))


def test_chunks_empty_when_not_advancing() -> None:
    assert list(_date_chunks(JAN1, JAN1, 7)) == []  # backfill() widens equal bounds
