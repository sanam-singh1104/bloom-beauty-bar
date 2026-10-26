import os
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter, SimpleLogRecordProcessor
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app import telemetry
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


@dataclass
class Telemetry:
    spans: InMemorySpanExporter
    metrics: InMemoryMetricReader
    logs: InMemoryLogRecordExporter


@pytest.fixture(scope="session")
def _session_telemetry():
    """Install in-memory exporters before the app does, so nothing hits the console.

    Providers are global and can only be set once, so this is session-wide.
    """
    captured = Telemetry(
        InMemorySpanExporter(), InMemoryMetricReader(), InMemoryLogRecordExporter()
    )
    telemetry.configure(
        span_processor=SimpleSpanProcessor(captured.spans),
        metric_reader=captured.metrics,
        log_processor=SimpleLogRecordProcessor(captured.logs),
    )
    return captured


@pytest.fixture(autouse=True)
def captured_telemetry(_session_telemetry):
    """Spans and logs from this test only. Metrics are cumulative across tests."""
    _session_telemetry.spans.clear()
    _session_telemetry.logs.clear()
    return _session_telemetry
