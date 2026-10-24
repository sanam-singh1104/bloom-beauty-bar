import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.sql_store import Base, SqlStore

TESTS_DIR = Path(__file__).parent


def pytest_collection_modifyitems(items):
    """Mark tests by folder so `-m unit` / `-m integration` work."""
    for item in items:
        folder = Path(item.fspath).relative_to(TESTS_DIR).parts[0]
        if folder in ("unit", "integration"):
            item.add_marker(folder)


def _reset_schema(database_url: str) -> None:
    """Drop every table (and its id sequence) so the next test starts empty."""
    store = SqlStore(database_url)
    try:
        Base.metadata.drop_all(store.engine)
    finally:
        store.close()


@pytest.fixture
def database_url(tmp_path):
    """A fresh, empty database per test.

    A new SQLite file by default. Set TEST_DATABASE_URL (e.g. to a Postgres URL,
    as CI does) to run against that database instead; it's wiped before and
    after each test, so never point it at real data.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        yield f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
        return
    _reset_schema(url)
    yield url
    _reset_schema(url)


@pytest.fixture
def client(database_url, monkeypatch):
    """The real app, started against that test's own database."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    with TestClient(app) as client:
        yield client
