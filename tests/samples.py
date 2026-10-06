"""Sample payloads shared by tests. T1/T2 are the two trips from the assignment."""

from app.models import Trip

T1 = {
    "id": "t1",
    "start": "2026-10-01T08:10:00+05:00",
    "end": "2026-10-01T08:32:00+05:00",
    "amount": 2400,
    "payment": "card",
    "commission": 360,
}
T2 = {
    "id": "t2",
    "start": "2026-10-01T09:05:00+05:00",
    "end": "2026-10-01T09:20:00+05:00",
    "amount": 1500,
    "payment": "cash",
    "commission": 225,
}


def payload(**overrides) -> dict:
    """T1 without id, with fields overridden (an `id=` override is kept)."""
    data = {k: v for k, v in T1.items() if k != "id"}
    data.update(overrides)
    return data


def trip(**overrides) -> Trip:
    """A validated Trip based on T1; `id` defaults to "t1"."""
    data = {**T1}
    data.update(overrides)
    return Trip.model_validate(data)
