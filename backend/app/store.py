"""Storage interface. Endpoints depend on this, not on a specific backend."""

from typing import Protocol

from .models import Booking, BookingCreate, Service

SEED_SERVICES = [
    ("Haircut", 30, 150),
    ("Hair Colour", 90, 450),
    ("Root Touch-Up", 60, 300),
    ("Manicure", 45, 200),
    ("Pedicure", 60, 280),
    ("Facial", 60, 350),
]


class Store(Protocol):
    def init(self) -> None:
        """Create the schema if needed and seed the services."""

    def close(self) -> None: ...

    def list_services(self) -> list[Service]: ...

    def get_service(self, service_id: int) -> Service | None: ...

    def create_booking(self, booking: BookingCreate) -> Booking: ...

    def list_bookings(self) -> list[Booking]: ...

    def delete_booking(self, booking_id: int) -> bool:
        """Delete a booking. Returns False if it didn't exist."""
