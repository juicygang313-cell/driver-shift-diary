"""Day summary: a pure function over trips, no I/O."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from decimal import Decimal

from app.models import DaySummary, PaymentTotal, Trip

ZERO = Decimal(0)
PAYMENTS = ("cash", "card")


def build_summary(trips: Iterable[Trip], day: dt.date) -> DaySummary:
    """Summary for `day`: trips whose start date (in its own offset) equals `day`."""
    counts = {p: 0 for p in PAYMENTS}
    amounts = {p: ZERO for p in PAYMENTS}
    revenue = ZERO
    commission = ZERO
    trips_count = 0

    for t in trips:
        if t.day != day:
            continue
        trips_count += 1
        revenue += t.amount
        commission += t.commission
        counts[t.payment] += 1
        amounts[t.payment] += t.amount

    return DaySummary(
        date=day,
        trips_count=trips_count,
        revenue=revenue,
        commission=commission,
        net=revenue - commission,
        by_payment={p: PaymentTotal(count=counts[p], amount=amounts[p]) for p in PAYMENTS},
    )
