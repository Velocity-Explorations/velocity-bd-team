"""Deadlines as portals write them, for Discovery's default result date and the internal submit-by date."""
from __future__ import annotations

from datetime import date, datetime, timezone

from drafting import dates


def test_portal_text_and_iso_deadlines_parse_to_utc() -> None:
    assert dates.parse_due("30 OCT 2026 : 21:59 MDT") == datetime(2026, 10, 31, 3, 59, tzinfo=timezone.utc)
    assert dates.parse_due("2026-11-01") == datetime(2026, 11, 1, 23, 59, tzinfo=timezone.utc)
    assert dates.parse_due("2026-11-05T17:00:00-05:00") == datetime(2026, 11, 5, 22, 0, tzinfo=timezone.utc)
    assert dates.parse_due("when funds allow") is None and dates.parse_due(None) is None


def test_the_deadline_day_is_the_day_in_denver() -> None:
    assert dates.deadline_day("30 OCT 2026 : 21:59 MDT") == date(2026, 10, 30)
    assert dates.deadline_day("2026-11-01") == date(2026, 11, 1)
    assert dates.deadline_day("rolling") is None


def test_submit_by_is_one_business_day_before() -> None:
    assert dates.business_day_before(date(2026, 11, 4)) == date(2026, 11, 3)    # Wednesday to Tuesday
    assert dates.business_day_before(date(2026, 11, 2)) == date(2026, 10, 30)   # Monday to the Friday before
    assert dates.business_day_before(date(2026, 11, 1)) == date(2026, 10, 30)   # Sunday to Friday
