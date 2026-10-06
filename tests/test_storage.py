import json
import threading
import time
from datetime import date

import pytest

from app.models import TripIn
from app.storage import SEED_FILE, StorageError, TripStorage
from tests.samples import T1, T2, payload


def tin(**overrides) -> TripIn:
    return TripIn.model_validate(payload(**overrides))


@pytest.fixture
def storage(tmp_path):
    return TripStorage(tmp_path / "trips.json", seed=None)


def test_add_creates_and_persists(storage, tmp_path):
    trip, status = storage.add(tin(id="t1"))
    assert status == "created"
    assert trip.id == "t1"
    on_disk = json.loads((tmp_path / "trips.json").read_text(encoding="utf-8"))
    assert on_disk == [T1]
    reloaded = TripStorage(tmp_path / "trips.json", seed=None)
    assert [t.id for t in reloaded.all()] == ["t1"]


def test_repeat_with_same_id_and_content_is_existing(storage):
    storage.add(tin(id="t1"))
    trip, status = storage.add(tin(id="t1"))
    assert status == "existing"
    assert trip.id == "t1"
    assert len(storage.all()) == 1


def test_repeat_without_id_same_content_is_existing(storage):
    first, _ = storage.add(tin())
    second, status = storage.add(tin())
    assert status == "existing"
    assert second.id == first.id
    assert len(storage.all()) == 1


def test_new_id_but_same_content_is_existing(storage):
    first, _ = storage.add(tin(id="t1"))
    second, status = storage.add(tin(id="other"))
    assert status == "existing"
    assert second.id == "t1"
    assert len(storage.all()) == 1


def test_same_id_different_content_is_conflict(storage):
    storage.add(tin(id="t1"))
    trip, status = storage.add(tin(id="t1", amount=9999, commission=0))
    assert status == "conflict"
    assert trip.amount == 2400  # the existing record, unchanged
    assert len(storage.all()) == 1


def test_two_different_trips_get_different_ids(storage):
    a, _ = storage.add(tin())
    b, _ = storage.add(tin(amount=100, commission=0))
    assert a.id != b.id
    assert len(storage.all()) == 2


def test_concurrent_identical_adds_create_one_record(storage, monkeypatch):
    n = 8
    barrier = threading.Barrier(n)
    statuses: list[str] = []
    real_write = storage._write

    def slow_write(trips):
        time.sleep(0.05)  # widen the check-then-act window so a missing lock shows up
        real_write(trips)

    monkeypatch.setattr(storage, "_write", slow_write)

    def worker():
        barrier.wait()
        _, status = storage.add(tin())
        statuses.append(status)

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(storage.all()) == 1
    assert sorted(statuses) == ["created"] + ["existing"] * (n - 1)


def test_failed_write_does_not_change_memory(storage, tmp_path, monkeypatch):
    def boom(src, dst):
        raise PermissionError("locked")

    monkeypatch.setattr("app.storage.os.replace", boom)
    with pytest.raises(PermissionError):
        storage.add(tin())
    assert storage.all() == []
    assert not list(tmp_path.glob(".trips-*.json"))  # temp file cleaned up
    monkeypatch.undo()
    _, status = storage.add(tin())
    assert status == "created"


def test_invalid_file_fails_fast(tmp_path):
    path = tmp_path / "trips.json"
    path.write_text('{"not": "a list"}', encoding="utf-8")
    with pytest.raises(StorageError):
        TripStorage(path, seed=None)


def test_missing_file_is_copied_from_seed(tmp_path):
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps([T1, T2]), encoding="utf-8")
    storage = TripStorage(tmp_path / "data" / "trips.json", seed=seed)
    assert [t.id for t in storage.all()] == ["t1", "t2"]
    assert (tmp_path / "data" / "trips.json").exists()


def test_missing_file_and_missing_seed_start_empty(tmp_path):
    storage = TripStorage(tmp_path / "trips.json", seed=tmp_path / "nope.json")
    assert storage.all() == []


def test_shipped_seed_is_valid(tmp_path):
    storage = TripStorage(tmp_path / "trips.json", seed=SEED_FILE)
    assert len(storage.all()) == 11
    assert [d for d, _ in storage.days()] == [date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3)]


def test_for_date_sorted_by_wall_clock_start(storage):
    storage.add(tin(id="late", start="2026-10-01T18:00:00+05:00", end="2026-10-01T18:30:00+05:00"))
    storage.add(tin(id="early", start="2026-10-01T08:00:00+05:00", end="2026-10-01T08:30:00+05:00"))
    assert [t.id for t in storage.for_date(date(2026, 10, 1))] == ["early", "late"]
    assert storage.for_date(date(2026, 10, 2)) == []


def test_days_lists_dates_with_counts(storage):
    storage.add(tin(id="a"))
    storage.add(tin(id="b", start="2026-10-03T08:00:00+05:00", end="2026-10-03T08:30:00+05:00"))
    storage.add(tin(id="c", start="2026-10-03T09:00:00+05:00", end="2026-10-03T09:30:00+05:00"))
    assert storage.days() == [(date(2026, 10, 1), 1), (date(2026, 10, 3), 2)]
