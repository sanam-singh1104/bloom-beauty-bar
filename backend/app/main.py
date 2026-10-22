import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from .errors import describe_errors, field_error, validation_error
from .models import Booking, BookingCreate, Service
from .sql_store import DEFAULT_DATABASE_URL, SqlStore
from .store import Store

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = SqlStore(os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))
    store.init()
    app.state.store = store
    yield
    store.close()


app = FastAPI(title="Bloom Beauty Bar API", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    return validation_error(describe_errors(exc.errors()))


def get_store(request: Request) -> Store:
    return request.app.state.store


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/services", response_model=list[Service])
def list_services(store: Store = Depends(get_store)) -> list[Service]:
    return store.list_services()


@app.post(
    "/api/bookings",
    response_model=Booking,
    status_code=status.HTTP_201_CREATED,
    responses={422: {"description": "Missing or invalid fields"}},
)
def create_booking(booking: BookingCreate, store: Store = Depends(get_store)):
    if store.get_service(booking.service_id) is None:
        return validation_error([field_error("service_id", "The selected service doesn't exist")])
    return store.create_booking(booking)


@app.get("/api/bookings", response_model=list[Booking])
def list_bookings(store: Store = Depends(get_store)) -> list[Booking]:
    return store.list_bookings()


@app.delete(
    "/api/bookings/{booking_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Booking not found"}},
)
def cancel_booking(booking_id: int, store: Store = Depends(get_store)) -> Response:
    if not store.delete_booking(booking_id):
        raise HTTPException(status_code=404, detail="Booking not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Serve the frontend from the same origin so it can call /api without CORS.
# Mounted last so it doesn't shadow the API routes.
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
