import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .models import Booking, BookingCreate, Service
from .sql_store import DEFAULT_DATABASE_URL, SqlStore
from .store import Store

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

# Customer-facing names for request fields, used in error messages.
FIELD_LABELS = {
    "service_id": "service",
    "starts_at": "date and time",
    "customer_name": "name",
    "customer_contact": "contact",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = SqlStore(os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))
    store.init()
    app.state.store = store
    yield
    store.close()


app = FastAPI(title="Bloom Beauty Bar API", lifespan=lifespan)


def validation_error(errors: list[dict]) -> JSONResponse:
    """422 with a one-line `detail` for people and per-field `errors` for code.

    Each error is {"field", "message", "missing": bool}.
    """
    missing = [FIELD_LABELS.get(e["field"], e["field"]) for e in errors if e["missing"]]
    parts = []
    if missing:
        parts.append(f"Please provide: {', '.join(missing)}.")
    parts += [e["message"] + "." for e in errors if not e["missing"]]
    return JSONResponse(
        status_code=422,
        content={"detail": " ".join(parts), "errors": errors},
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        if err["type"] == "json_invalid" or err["loc"] == ("body",):
            errors.append({"field": "body", "message": "Request body must be a JSON object", "missing": False})
            continue
        field = str(err["loc"][-1])
        label = FIELD_LABELS.get(field, field)
        value = err.get("input")
        is_missing = (
            err["type"] == "missing"
            or value is None
            or (isinstance(value, str) and not value.strip())
        )
        if is_missing:
            message = "Field required"
        elif err["type"] == "value_error":
            message = err["msg"].removeprefix("Value error, ")
        else:
            message = f"Invalid {label}: {err['msg']}"
        errors.append({"field": field, "message": message, "missing": is_missing})
    return validation_error(errors)


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
        return validation_error(
            [{"field": "service_id", "message": "The selected service doesn't exist", "missing": False}]
        )
    return store.create_booking(booking)


# Serve the frontend from the same origin so it can call /api without CORS.
# Mounted last so it doesn't shadow the API routes.
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
