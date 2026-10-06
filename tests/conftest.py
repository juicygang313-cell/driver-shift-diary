import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.storage import TripStorage


@pytest.fixture
def storage(tmp_path):
    return TripStorage(tmp_path / "trips.json", seed=None)


@pytest.fixture
def client(storage):
    return TestClient(create_app(storage))
