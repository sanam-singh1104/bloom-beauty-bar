from datetime import datetime

from pydantic import BaseModel


class Service(BaseModel):
    id: int
    name: str
    duration_minutes: int
    price_rand: int


class BookingCreate(BaseModel):
    service_id: int
    starts_at: datetime
    customer_name: str
    customer_contact: str


class Booking(BookingCreate):
    id: int
    created_at: datetime
