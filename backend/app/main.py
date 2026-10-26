import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from . import telemetry
from .errors import describe_errors, field_error, validation_error
from .models import Booking, BookingCreate, Service
from .sql_store import DEFAULT_DATABASE_URL, SqlStore
from .store import Store

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    telemetry.configure()
    store = SqlStore(os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))
    store.init()
    app.state.store = store
    yield
    store.close()


# FastAPI's built-in telemetry is off: it records client addresses, user agents
# and validation errors with the submitted values (customer data). Our own
# middleware and spans (app/telemetry.py) emit only what we choose.
app = FastAPI(
    title="Bloom Beauty Bar API",
    lifespan=lifespan,
    telemetry={"tracing": False, "metrics": False, "logs": False, "operation_spans": False},
)
app.add_middleware(telemetry.TelemetryMiddleware)


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    errors = describe_errors(exc.errors())
    if request.method == "POST" and request.url.path == "/api/bookings":
        _reject_booking("invalid", errors)
    return validation_error(errors)


def _reject_booking(reason: str, errors: list[dict]) -> None:
    # Field names only; the submitted values are customer data.
    fields = sorted({e["field"] for e in errors})
    telemetry.bookings_rejected.add(1, {"reason": reason})
    telemetry.logger.warning(
        "Booking rejected: %s (%s)",
        reason,
        ", ".join(fields),
        extra={"booking.reject_reason": reason, "booking.invalid_fields": fields},
    )


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
    with telemetry.span("create_booking") as span:
        span.set_attribute("booking.service_id", booking.service_id)
        if store.get_service(booking.service_id) is None:
            errors = [field_error("service_id", "The selected service doesn't exist")]
            _reject_booking("unknown_service", errors)
            return validation_error(errors)
        saved = store.create_booking(booking)
        span.set_attribute("booking.id", saved.id)
        telemetry.bookings_created.add(1, {"booking.service_id": saved.service_id})
        telemetry.logger.info(
            "Booking created: id=%s service_id=%s",
            saved.id,
            saved.service_id,
            extra={"booking.id": saved.id, "booking.service_id": saved.service_id},
        )
        return saved


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
