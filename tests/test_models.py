from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models import Trip, TripIn
from tests.samples import T1, payload


def test_valid_payload_parses_example_trip():
    t = TripIn.model_validate(T1)
    assert t.id == "t1"
    assert t.amount == Decimal("2400")
    assert t.payment == "card"
    assert t.day.isoformat() == "2026-10-01"


def test_id_is_optional_and_null_means_absent():
    assert TripIn.model_validate(payload()).id is None
    assert TripIn.model_validate(payload(id=None)).id is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": 0},
        {"amount": -5},
        {"amount": float("inf")},
        {"amount": "2400.555"},
        {"amount": "2400,50"},
        {"commission": -1},
        {"commission": 2401},
        {"end": "2026-10-01T08:10:00+05:00"},  # end == start
        {"end": "2026-10-01T08:00:00+05:00"},  # end < start
        {"start": "2026-10-01T08:10:00"},  # naive
        {"payment": "crypto"},
        {"payment": "Card"},
        {"id": ""},
        {"id": "<img src=x>"},
        {"id": 123},
        {"id": "x" * 65},
        {"extra_field": 1},
    ],
    ids=str,
)
def test_invalid_payload_rejected(overrides):
    with pytest.raises(ValidationError):
        TripIn.model_validate(payload(**overrides))


def test_validator_messages_do_not_echo_input():
    with pytest.raises(ValidationError) as exc:
        TripIn.model_validate(payload(end="2026-10-01T08:00:00+05:00"))
    messages = " ".join(e["msg"] for e in exc.value.errors())
    assert "end must be after start" in messages
    assert "2026-10-01" not in messages


def test_money_serializes_as_number():
    whole = TripIn.model_validate(payload(amount=2400)).model_dump(mode="json")
    fraction = TripIn.model_validate(payload(amount="2400.50")).model_dump(mode="json")
    assert whole["amount"] == 2400 and isinstance(whole["amount"], int)
    assert fraction["amount"] == 2400.5


def test_content_key_compares_parsed_values():
    a = TripIn.model_validate(payload(amount=2400))
    b = TripIn.model_validate(payload(amount="2400.0", start="2026-10-01T03:10:00Z"))
    assert a.content_key() == b.content_key()


def test_end_in_other_offset_is_compared_as_instant():
    # 03:20Z == 08:20+05:00, which is after start 08:10+05:00
    t = TripIn.model_validate(payload(end="2026-10-01T03:20:00Z"))
    assert t.end > t.start


def test_trip_from_input_generates_uuid_when_id_missing():
    a = Trip.from_input(TripIn.model_validate(payload()))
    b = Trip.from_input(TripIn.model_validate(payload()))
    assert len(a.id) == 36
    assert a.id != b.id


def test_trip_from_input_keeps_given_id():
    assert Trip.from_input(TripIn.model_validate(T1)).id == "t1"
