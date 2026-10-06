from datetime import date
from decimal import Decimal

from app.summary import build_summary
from tests.samples import T1, T2, trip

D = date(2026, 10, 1)


def test_example_day_summary():
    s = build_summary([trip(**T1), trip(**T2)], D)
    assert s.model_dump(mode="json") == {
        "date": "2026-10-01",
        "trips_count": 2,
        "revenue": 3900,
        "commission": 585,
        "net": 3315,
        "by_payment": {
            "cash": {"count": 1, "amount": 1500},
            "card": {"count": 1, "amount": 2400},
        },
    }


def test_empty_day_is_all_zeros():
    s = build_summary([], D)
    assert s.model_dump(mode="json") == {
        "date": "2026-10-01",
        "trips_count": 0,
        "revenue": 0,
        "commission": 0,
        "net": 0,
        "by_payment": {
            "cash": {"count": 0, "amount": 0},
            "card": {"count": 0, "amount": 0},
        },
    }


def test_missing_payment_type_still_present_with_zeros():
    s = build_summary([trip(**T1)], D)  # card only
    assert s.by_payment["cash"].count == 0
    assert s.by_payment["cash"].amount == 0
    assert s.by_payment["card"].count == 1


def test_other_day_trip_is_excluded():
    other = trip(id="x", start="2026-10-02T08:10:00+05:00", end="2026-10-02T08:32:00+05:00")
    s = build_summary([trip(**T1), other], D)
    assert s.trips_count == 1
    assert s.revenue == 2400


def test_trip_crossing_midnight_belongs_to_start_day():
    night = trip(id="n", start="2026-10-01T23:50:00+05:00", end="2026-10-02T00:10:00+05:00")
    assert build_summary([night], D).trips_count == 1
    assert build_summary([night], date(2026, 10, 2)).trips_count == 0


def test_same_calendar_date_in_different_offsets_both_counted():
    a = trip(id="a", start="2026-10-01T08:10:00+05:00", end="2026-10-01T08:32:00+05:00")
    b = trip(id="b", start="2026-10-01T08:10:00+03:00", end="2026-10-01T08:32:00+03:00")
    assert build_summary([a, b], D).trips_count == 2


def test_day_is_wall_clock_date_not_utc():
    # 02:00+05:00 on Oct 1 is 21:00 UTC on Sep 30 — it must count on Oct 1.
    early = trip(id="e", start="2026-10-01T02:00:00+05:00", end="2026-10-01T02:20:00+05:00")
    assert build_summary([early], D).trips_count == 1
    assert build_summary([early], date(2026, 9, 30)).trips_count == 0


def test_fractional_amounts_sum_exactly():
    a = trip(id="a", amount="0.1", commission="0")
    b = trip(id="b", amount="0.2", commission="0")
    s = build_summary([a, b], D)
    assert s.revenue == Decimal("0.3")
    assert s.model_dump(mode="json")["revenue"] == 0.3
