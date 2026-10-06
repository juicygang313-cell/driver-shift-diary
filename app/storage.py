"""JSON-file storage for trips with duplicate protection."""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Literal

from pydantic import TypeAdapter, ValidationError

from app.models import Trip, TripIn

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRIPS_FILE = PACKAGE_ROOT / "data" / "trips.json"
SEED_FILE = PACKAGE_ROOT / "data" / "seed.json"

AddStatus = Literal["created", "existing", "conflict"]

_TRIPS = TypeAdapter(list[Trip])


class StorageError(Exception):
    """The trips file could not be read or is not a valid trip list."""


class TripStorage:
    """All trips live in memory; every add rewrites the file atomically.

    One process, one worker: the file must not be edited while the server runs.
    """

    def __init__(self, path: Path, seed: Path | None = SEED_FILE) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists() and seed is not None and seed.exists():
            shutil.copyfile(seed, self._path)
        self._trips: list[Trip] = self._load()

    def _load(self) -> list[Trip]:
        if not self._path.exists():
            return []
        try:
            return _TRIPS.validate_json(self._path.read_bytes())
        except (ValidationError, ValueError) as exc:
            raise StorageError(f"Invalid trips file {self._path}: {exc}") from exc

    def all(self) -> list[Trip]:
        return list(self._trips)

    def for_date(self, day: dt.date) -> list[Trip]:
        """Trips of `day`, ordered by wall-clock start (consistent with day grouping)."""
        return sorted(
            (t for t in self._trips if t.day == day),
            key=lambda t: t.start.replace(tzinfo=None),
        )

    def days(self) -> list[tuple[dt.date, int]]:
        counts: dict[dt.date, int] = {}
        for t in self._trips:
            counts[t.day] = counts.get(t.day, 0) + 1
        return sorted(counts.items())

    def add(self, trip_in: TripIn) -> tuple[Trip, AddStatus]:
        """Store `trip_in` unless it duplicates an existing trip.

        Same id + same content -> existing; same id + different content -> conflict
        (nothing written); same content under any/no id -> existing; else created.

        All operations (detect, write, publish) happen inside the lock. If write fails,
        memory and disk stay in sync: trip is not added to either.
        """
        with self._lock:
            if trip_in.id is not None:
                by_id = next((t for t in self._trips if t.id == trip_in.id), None)
                if by_id is not None:
                    if by_id.content_key() == trip_in.content_key():
                        return by_id, "existing"
                    return by_id, "conflict"

            key = trip_in.content_key()
            by_content = next((t for t in self._trips if t.content_key() == key), None)
            if by_content is not None:
                return by_content, "existing"

            trip = Trip.from_input(trip_in)
            new_trips = [*self._trips, trip]
            self._write(new_trips)
            self._trips = new_trips
            return trip, "created"

    def _write(self, trips: list[Trip]) -> None:
        """Write trips to a temp file in the same directory, then replace (atomic on Windows too).

        Must be called inside the lock. Takes a list instead of using self._trips to prevent
        partial updates if write fails: caller only commits the new list to memory after success.
        """
        payload = [t.model_dump(mode="json") for t in trips]
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, prefix=".trips-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self._path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
