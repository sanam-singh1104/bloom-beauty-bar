"""In-memory data store. Replaced by a real database in issue #6."""

from .models import Service

SEED_SERVICES = [
    ("Haircut", 30, 150),
    ("Hair Colour", 90, 450),
    ("Root Touch-Up", 60, 300),
    ("Manicure", 45, 200),
    ("Pedicure", 60, 280),
    ("Facial", 60, 350),
]


class InMemoryStore:
    def __init__(self) -> None:
        self.services: list[Service] = []

    def seed(self) -> None:
        self.services = [
            Service(id=i, name=name, duration_minutes=duration, price_rand=price)
            for i, (name, duration, price) in enumerate(SEED_SERVICES, start=1)
        ]

    def list_services(self) -> list[Service]:
        return list(self.services)
