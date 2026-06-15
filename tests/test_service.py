"""Collect loop helpers: the resume/catch-up window computation."""

import datetime as dt
from zoneinfo import ZoneInfo

from fluvilog.service import _catchup_window

BERLIN = ZoneInfo("Europe/Berlin")
TODAY = dt.date(2026, 6, 15)


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


def test_caught_up_today_still_spans_one_day() -> None:
    # von < bis is required upstream, so even a same-day watermark looks back a day.
    assert _catchup_window(_ts(TODAY), TODAY, cap_days=7) == (
        TODAY - dt.timedelta(days=1),
        TODAY,
    )
