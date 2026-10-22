from datetime import datetime

import pytest

from app.models import BookingCreate
from app.sql_store import SqlStore


@pytest.fixture
def open_store(database_url):
    """Opens stores on the same database file, simulating app restarts."""
    stores = []

    def _open() -> SqlStore:
        store = SqlStore(database_url)
        store.init()
        stores.append(store)
        return store

    yield _open
    for store in stores:
        store.close()


def make_booking(service_id: int = 1) -> BookingCreate:
    return BookingCreate(
        service_id=service_id,
        starts_at=datetime(2026, 11, 3, 10, 30),
        customer_name="Thandi M",
        customer_contact="082 555 0101",
    )


def test_seeding_is_idempotent_across_restarts(open_store):
    first = open_store().list_services()
    second = open_store().list_services()
    assert len(first) == 6
    assert second == first


def test_bookings_persist_across_restarts(open_store):
    created = open_store().create_booking(make_booking())
    bookings = open_store().list_bookings()
    assert bookings == [created]
    assert bookings[0].customer_name == "Thandi M"
    assert bookings[0].starts_at == datetime(2026, 11, 3, 10, 30)


def test_delete_booking(open_store):
    store = open_store()
    booking = store.create_booking(make_booking())
    assert store.delete_booking(booking.id) is True
    assert store.list_bookings() == []
    assert store.delete_booking(booking.id) is False


def test_get_service(open_store):
    store = open_store()
    assert store.get_service(1).name == "Haircut"
    assert store.get_service(999) is None
