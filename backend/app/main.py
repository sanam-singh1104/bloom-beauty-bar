import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles

from .models import Service
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


def get_store(request: Request) -> Store:
    return request.app.state.store


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/services", response_model=list[Service])
def list_services(store: Store = Depends(get_store)) -> list[Service]:
    return store.list_services()


# Serve the frontend from the same origin so it can call /api without CORS.
# Mounted last so it doesn't shadow the API routes.
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
