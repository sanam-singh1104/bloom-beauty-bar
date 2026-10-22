from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .models import Service
from .store import InMemoryStore

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"

store = InMemoryStore()


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.seed()
    yield


app = FastAPI(title="Bloom Beauty Bar API", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/services", response_model=list[Service])
def list_services() -> list[Service]:
    return store.list_services()


# Serve the frontend from the same origin so it can call /api without CORS.
# Mounted last so it doesn't shadow the API routes.
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
