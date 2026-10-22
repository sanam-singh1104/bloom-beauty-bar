"""SQLAlchemy implementation of Store. Works with SQLite or Postgres via the URL."""

from datetime import datetime
from pathlib import Path

from sqlalchemy import DateTime, ForeignKey, String, create_engine, make_url, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .models import Booking, BookingCreate, Service
from .store import SEED_SERVICES

DEFAULT_DATABASE_URL = (
    f"sqlite:///{(Path(__file__).resolve().parents[1] / 'data' / 'bloom.db').as_posix()}"
)


class Base(DeclarativeBase):
    pass


class ServiceRow(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    duration_minutes: Mapped[int]
    price_rand: Mapped[int]


class BookingRow(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    customer_name: Mapped[str] = mapped_column(String(200))
    customer_contact: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


def _to_service(row: ServiceRow) -> Service:
    return Service(
        id=row.id,
        name=row.name,
        duration_minutes=row.duration_minutes,
        price_rand=row.price_rand,
    )


def _to_booking(row: BookingRow) -> Booking:
    return Booking(
        id=row.id,
        service_id=row.service_id,
        starts_at=row.starts_at,
        customer_name=row.customer_name,
        customer_contact=row.customer_contact,
        created_at=row.created_at,
    )


class SqlStore:
    def __init__(self, database_url: str = DEFAULT_DATABASE_URL) -> None:
        url = make_url(database_url)
        connect_args = {}
        if url.get_backend_name() == "sqlite":
            # FastAPI runs sync endpoints in a threadpool.
            connect_args["check_same_thread"] = False
            if url.database and url.database != ":memory:":
                Path(url.database).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url, connect_args=connect_args)
        self.Session = sessionmaker(self.engine, expire_on_commit=False)

    def init(self) -> None:
        Base.metadata.create_all(self.engine)
        self._seed_services()

    def close(self) -> None:
        self.engine.dispose()

    def _seed_services(self) -> None:
        # Idempotent: only adds services that aren't there yet, by name.
        with self.Session.begin() as session:
            existing = set(session.scalars(select(ServiceRow.name)))
            for name, duration, price in SEED_SERVICES:
                if name not in existing:
                    session.add(
                        ServiceRow(name=name, duration_minutes=duration, price_rand=price)
                    )

    def list_services(self) -> list[Service]:
        with self.Session() as session:
            rows = session.scalars(select(ServiceRow).order_by(ServiceRow.id))
            return [_to_service(r) for r in rows]

    def get_service(self, service_id: int) -> Service | None:
        with self.Session() as session:
            row = session.get(ServiceRow, service_id)
            return _to_service(row) if row else None

    def create_booking(self, booking: BookingCreate) -> Booking:
        with self.Session.begin() as session:
            row = BookingRow(**booking.model_dump())
            session.add(row)
            session.flush()
            return _to_booking(row)

    def list_bookings(self) -> list[Booking]:
        with self.Session() as session:
            rows = session.scalars(select(BookingRow).order_by(BookingRow.starts_at))
            return [_to_booking(r) for r in rows]

    def delete_booking(self, booking_id: int) -> bool:
        with self.Session.begin() as session:
            row = session.get(BookingRow, booking_id)
            if row is None:
                return False
            session.delete(row)
            return True
