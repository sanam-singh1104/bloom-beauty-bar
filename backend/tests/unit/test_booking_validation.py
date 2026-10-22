"""Booking validation rules on the model itself, no app or database."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.models import BookingCreate

VALID = {
    "service_id": 1,
    "starts_at": "2026-11-03T10:30",
    "customer_name": "Thandi M",
    "customer_contact": "082 555 0101",
}


def errors_for(**overrides) -> dict[str, dict]:
    """Validate VALID + overrides; return {field: pydantic error}."""
    with pytest.raises(ValidationError) as exc:
        BookingCreate(**{**VALID, **overrides})
    return {str(e["loc"][-1]): e for e in exc.value.errors()}


def test_valid_booking_parses():
    booking = BookingCreate(**VALID)
    assert booking.service_id == 1
    assert booking.starts_at == datetime(2026, 11, 3, 10, 30)


def test_name_and_contact_are_trimmed():
    booking = BookingCreate(
        **{**VALID, "customer_name": "  Thandi  ", "customer_contact": " a@b.co "}
    )
    assert booking.customer_name == "Thandi"
    assert booking.customer_contact == "a@b.co"


@pytest.mark.parametrize("field", ["service_id", "starts_at", "customer_name", "customer_contact"])
def test_absent_field_is_missing(field):
    data = {k: v for k, v in VALID.items() if k != field}
    with pytest.raises(ValidationError) as exc:
        BookingCreate(**data)
    [error] = exc.value.errors()
    assert error["loc"] == (field,)
    assert error["type"] == "missing"


@pytest.mark.parametrize("field", ["customer_name", "customer_contact"])
@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_blank_text_is_reported_as_missing(field, blank):
    errors = errors_for(**{field: blank})
    assert errors[field]["type"] == "missing"


@pytest.mark.parametrize(
    "contact",
    [
        "thandi@example.com",
        "first.last+salon@mail.co.za",
        "0825550101",
        "082 555 0101",
        "+27 82 555 0101",
        "(021) 555-0101",
    ],
)
def test_accepts_phone_or_email(contact):
    assert BookingCreate(**{**VALID, "customer_contact": contact}).customer_contact == contact


@pytest.mark.parametrize(
    "contact",
    [
        "call me",
        "thandi@",
        "@example.com",
        "thandi@example",
        "12345",  # too few digits
        "1234567890123456",  # too many digits
        "082-CALL-NOW",
    ],
)
def test_rejects_contact_that_is_not_phone_or_email(contact):
    error = errors_for(customer_contact=contact)["customer_contact"]
    assert error["type"] == "value_error"
    assert "valid phone number or email" in error["msg"]


def test_rejects_overlong_name():
    error = errors_for(customer_name="x" * 201)["customer_name"]
    assert "200 characters" in error["msg"]


@pytest.mark.parametrize("value", ["next tuesday", "2026-13-01T10:00", "10:30"])
def test_rejects_unparseable_date_time(value):
    assert "starts_at" in errors_for(starts_at=value)
