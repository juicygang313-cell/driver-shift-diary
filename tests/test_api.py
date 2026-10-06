import importlib

import pytest
from fastapi.testclient import TestClient

from tests.samples import T1, T2, payload

JSON = {"Content-Type": "application/json"}


def post(client, body):
    return client.post("/api/trips", json=body)


def test_post_then_repeat_then_list(client):
    first = post(client, T1)
    assert first.status_code == 201
    assert first.json()["id"] == "t1"
    again = post(client, T1)
    assert again.status_code == 200
    assert again.json() == first.json()
    trips = client.get("/api/trips", params={"date": "2026-10-01"})
    assert trips.status_code == 200
    assert [t["id"] for t in trips.json()] == ["t1"]


def test_summary_updates_after_post(client):
    before = client.get("/api/summary", params={"date": "2026-10-01"}).json()
    assert before["trips_count"] == 0
    post(client, T1)
    post(client, T2)
    after = client.get("/api/summary", params={"date": "2026-10-01"}).json()
    assert after == {
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


def test_same_id_different_body_is_409(client):
    post(client, T1)
    res = post(client, {**T1, "amount": 9999})
    assert res.status_code == 409
    assert res.json()["amount"] == 2400


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": 0},
        {"amount": "2400.555"},
        {"end": T1["start"]},
        {"end": "2026-10-01T08:00:00+05:00"},
        {"start": "2026-10-01T08:10:00"},
        {"payment": "crypto"},
        {"commission": 2401},
        {"id": "<img src=x>"},
        {"typo": 1},
    ],
    ids=str,
)
def test_invalid_body_is_422(client, overrides):
    res = post(client, payload(**overrides))
    assert res.status_code == 422
    assert "detail" in res.json()


def test_huge_number_is_422(client):
    raw = (
        '{"start":"2026-10-01T08:10:00+05:00","end":"2026-10-01T08:32:00+05:00",'
        '"amount":1e309,"payment":"card","commission":0}'
    )
    res = client.post("/api/trips", content=raw, headers=JSON)
    assert res.status_code == 422


def test_trips_without_date_is_422(client):
    assert client.get("/api/trips").status_code == 422
    assert client.get("/api/summary").status_code == 422
    assert client.get("/api/trips", params={"date": "2026-10-01T10:00"}).status_code == 422


def test_days_endpoint(client):
    assert client.get("/api/days").json() == []
    post(client, T1)
    post(client, T2)
    post(client, {**T1, "id": "t3", "start": "2026-10-03T08:00:00+05:00", "end": "2026-10-03T08:20:00+05:00"})
    assert client.get("/api/days").json() == [
        {"date": "2026-10-01", "trips_count": 2},
        {"date": "2026-10-03", "trips_count": 1},
    ]


def test_trips_are_sorted_regardless_of_insert_order(client):
    post(client, T2)
    post(client, T1)
    ids = [t["id"] for t in client.get("/api/trips", params={"date": "2026-10-01"}).json()]
    assert ids == ["t1", "t2"]


def test_money_serialization(client):
    whole = post(client, payload(amount=2400)).json()
    fraction = post(client, payload(amount="2400.5", commission="0.25")).json()
    assert whole["amount"] == 2400
    assert fraction["amount"] == 2400.5
    assert fraction["commission"] == 0.25


def test_main_builds_app_from_trips_file_env(tmp_path, monkeypatch):
    path = tmp_path / "trips.json"
    path.write_text("[]", encoding="utf-8")
    monkeypatch.setenv("TRIPS_FILE", str(path))
    main = importlib.reload(importlib.import_module("app.main"))
    assert TestClient(main.app).get("/api/days").json() == []


def test_index_serves_client(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "Дневник смен водителя" in res.text