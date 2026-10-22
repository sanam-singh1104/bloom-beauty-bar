from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

TESTS_DIR = Path(__file__).parent


def pytest_collection_modifyitems(items):
    """Mark tests by folder so `-m unit` / `-m integration` work."""
    for item in items:
        folder = Path(item.fspath).relative_to(TESTS_DIR).parts[0]
        if folder in ("unit", "integration"):
            item.add_marker(folder)


@pytest.fixture
def database_url(tmp_path):
    """A fresh SQLite database file per test."""
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def client(database_url, monkeypatch):
    """The real app, started against that test's own database."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    with TestClient(app) as client:
        yield client
