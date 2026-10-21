from __future__ import annotations

from datetime import datetime, timezone

from assistant.dates import days_until, parse_due

UTC = timezone.utc


def test_portal_format_converts_the_zone_to_utc() -> None:
    assert parse_due("30 OCT 2026 : 21:59 MDT") == datetime(2026, 10, 31, 3, 59, tzinfo=UTC)
    assert parse_due("31 DEC 2026 : 20:59 MST") == datetime(2027, 1, 1, 3, 59, tzinfo=UTC)
    assert parse_due("25 Sep 2026 : 16:00 EDT") == datetime(2026, 9, 25, 20, 0, tzinfo=UTC)
    assert parse_due("04 Oct 2026 : 22:00 UTC") == datetime(2026, 10, 4, 22, 0, tzinfo=UTC)


def test_european_event_zones_convert_to_utc() -> None:
    assert parse_due("15 JUL 2026 : 15:00 BST") == datetime(2026, 7, 15, 14, 0, tzinfo=UTC)
    assert parse_due("28 OCT 2026 : 15:00 GMT") == datetime(2026, 10, 28, 15, 0, tzinfo=UTC)
    assert parse_due("10 JUN 2026 : 09:00 CEST") == datetime(2026, 6, 10, 7, 0, tzinfo=UTC)
    assert parse_due("10 DEC 2026 : 09:00 CET") == datetime(2026, 12, 10, 8, 0, tzinfo=UTC)


def test_missing_or_unknown_zone_is_read_as_utc() -> None:
    assert parse_due("30 OCT 2026 : 21:59") == datetime(2026, 10, 30, 21, 59, tzinfo=UTC)
    assert parse_due("30 OCT 2026 : 21:59 XYZ") == datetime(2026, 10, 30, 21, 59, tzinfo=UTC)


def test_iso_dates_and_times() -> None:
    assert parse_due("2026-11-01") == datetime(2026, 11, 1, 23, 59, tzinfo=UTC)   # date only: end of day
    assert parse_due("2026-11-01T17:00:00Z") == datetime(2026, 11, 1, 17, 0, tzinfo=UTC)


def test_text_that_is_not_a_date() -> None:
    for text in (None, "", "TBD", "Rolling", "31 FOO 2026 : 21:59 MDT", "32 OCT 2026 : 21:59 MDT"):
        assert parse_due(text) is None, text


def test_days_until_counts_whole_days_left() -> None:
    now = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
    assert days_until(datetime(2026, 10, 31, 3, 59, tzinfo=UTC), now) == 13
    assert days_until(datetime(2026, 10, 17, 23, 0, tzinfo=UTC), now) == 0
    assert days_until(datetime(2026, 10, 15, 12, 0, tzinfo=UTC), now) == -2
