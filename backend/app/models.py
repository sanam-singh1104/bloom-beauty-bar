import re
from datetime import datetime

from pydantic import BaseModel, field_validator
from pydantic_core import PydanticCustomError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[\d\s\-()]{7,20}$")


class Service(BaseModel):
    id: int
    name: str
    duration_minutes: int
    price_rand: int


def _required_text(value: str) -> str:
    value = value.strip()
    if not value:
        # Same error type as an absent field, so blanks are reported as missing.
        raise PydanticCustomError("missing", "Field required")
    return value


class BookingCreate(BaseModel):
    service_id: int
    starts_at: datetime
    customer_name: str
    customer_contact: str

    @field_validator("customer_name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        value = _required_text(value)
        if len(value) > 200:
            raise ValueError("Name must be 200 characters or fewer")
        return value

    @field_validator("customer_contact")
    @classmethod
    def _check_contact(cls, value: str) -> str:
        value = _required_text(value)
        digits = re.sub(r"\D", "", value)
        is_phone = PHONE_RE.match(value) and 7 <= len(digits) <= 15
        if not (EMAIL_RE.match(value) or is_phone):
            raise ValueError("Enter a valid phone number or email address")
        return value


class Booking(BookingCreate):
    id: int
    created_at: datetime
