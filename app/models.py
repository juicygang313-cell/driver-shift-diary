"""Pydantic models: trips, day summary, and the Money type."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    model_validator,
)

TRIP_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
Payment = Literal["cash", "card"]


def _money_to_json(value: Decimal) -> int | float:
    """2400.00 -> 2400, 2400.50 -> 2400.5 — matches the assignment's JSON."""
    if value == value.to_integral_value():
        return int(value)
    return float(value)


_MoneyJson = PlainSerializer(_money_to_json, return_type=int | float, when_used="json")


def _whole_kopecks(value: Decimal) -> Decimal:
    """Reject sub-kopeck amounts that slip past decimal_places via exponent underflow."""
    if value != value.quantize(Decimal("0.01")):
        raise ValueError("must have at most 2 decimal places")
    return value


# Exact decimal money: up to 2 decimal places, no inf/nan. Sums stay exact.
Money = Annotated[
    Decimal,
    Field(max_digits=12, decimal_places=2),
    AfterValidator(_whole_kopecks),
    _MoneyJson,
]
# Totals in summaries: same serialization, no digit limit.
MoneyTotal = Annotated[Decimal, _MoneyJson]


class TripIn(BaseModel):
    """A trip as sent by the client. `id` is optional."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = Field(default=None, pattern=TRIP_ID_PATTERN)
    start: AwareDatetime
    end: AwareDatetime
    amount: Money = Field(gt=0)
    payment: Payment
    commission: Money = Field(ge=0)

    @model_validator(mode="after")
    def _check_invariants(self) -> TripIn:
        if self.end <= self.start:
            raise ValueError("end must be after start")
        if self.commission > self.amount:
            raise ValueError("commission must not exceed amount")
        return self

    @property
    def day(self) -> dt.date:
        """Calendar date of `start` in the trip's own offset."""
        return self.start.date()

    def content_key(self) -> tuple:
        """What makes two trips 'the same' regardless of id."""
        return (self.start, self.end, self.amount, self.payment, self.commission)


class Trip(TripIn):
    """A stored trip: `id` is required."""

    id: str = Field(pattern=TRIP_ID_PATTERN)

    @classmethod
    def from_input(cls, trip_in: TripIn) -> Trip:
        data = trip_in.model_dump()
        data["id"] = trip_in.id or str(uuid.uuid4())
        return cls.model_validate(data)


class PaymentTotal(BaseModel):
    count: int
    amount: MoneyTotal


class DaySummary(BaseModel):
    date: dt.date
    trips_count: int
    revenue: MoneyTotal
    commission: MoneyTotal
    net: MoneyTotal
    by_payment: dict[Payment, PaymentTotal]


class DayInfo(BaseModel):
    date: dt.date
    trips_count: int
