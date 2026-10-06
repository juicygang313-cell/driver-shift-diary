"""ASGI entry point: `python -m uvicorn app.main:app`."""

import os
from pathlib import Path

from app.api import create_app
from app.storage import DEFAULT_TRIPS_FILE, TripStorage

app = create_app(TripStorage(Path(os.environ.get("TRIPS_FILE", DEFAULT_TRIPS_FILE))))
