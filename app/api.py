"""FastAPI application factory."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from fastapi import FastAPI, Query, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from app.models import DayInfo, DaySummary, Trip, TripIn
from app.storage import TripStorage
from app.summary import build_summary

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app(storage: TripStorage) -> FastAPI:
    app = FastAPI(title="Driver shift diary")

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI's default handler echoes each error's `input`; for `1e309` that is `inf`,
        # which JSON cannot encode, so a rejected request would turn into a 500.
        errors = [{k: v for k, v in err.items() if k != "input"} for err in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/days", response_model=list[DayInfo])
    def list_days() -> list[DayInfo]:
        return [DayInfo(date=day, trips_count=count) for day, count in storage.days()]

    @app.get("/api/trips", response_model=list[Trip])
    def list_trips(day: dt.date = Query(alias="date")) -> list[Trip]:
        return storage.for_date(day)

    @app.get("/api/summary", response_model=DaySummary)
    def day_summary(day: dt.date = Query(alias="date")) -> DaySummary:
        return build_summary(storage.for_date(day), day)

    @app.post("/api/trips", response_model=Trip, status_code=status.HTTP_201_CREATED)
    def add_trip(trip_in: TripIn, response: Response) -> Trip:
        trip, result = storage.add(trip_in)
        if result == "existing":
            response.status_code = status.HTTP_200_OK
        elif result == "conflict":
            response.status_code = status.HTTP_409_CONFLICT
        return trip

    return app
