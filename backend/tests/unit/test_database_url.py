"""DATABASE_URL values from hosts like Render are pointed at the psycopg driver."""

import pytest

from app.sql_store import normalize_database_url


@pytest.mark.parametrize(
    "given",
    [
        "postgresql://user:pass@host:5432/db",
        "postgres://user:pass@host:5432/db",
    ],
)
def test_bare_postgres_urls_use_psycopg(given):
    assert normalize_database_url(given) == "postgresql+psycopg://user:pass@host:5432/db"


@pytest.mark.parametrize(
    "given",
    [
        "postgresql+psycopg://user:pass@host:5432/db",
        "sqlite:////data/bloom.db",
        "sqlite:///:memory:",
    ],
)
def test_other_urls_are_unchanged(given):
    assert normalize_database_url(given) == given
