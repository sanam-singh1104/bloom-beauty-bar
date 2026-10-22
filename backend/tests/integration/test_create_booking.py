import pytest

VALID = {
    "service_id": 1,
    "starts_at": "2026-11-03T10:30",
    "customer_name": "Thandi M",
    "customer_contact": "082 555 0101",
}


def stored_bookings(client):
    return client.app.state.store.list_bookings()


def test_create_booking_saves_and_returns_it(client):
    response = client.post("/api/bookings", json=VALID)

    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["service_id"] == 1
    assert body["starts_at"] == "2026-11-03T10:30:00"
    assert body["customer_name"] == "Thandi M"
    assert body["customer_contact"] == "082 555 0101"

    [saved] = stored_bookings(client)
    assert saved.id == body["id"]


@pytest.mark.parametrize("contact", ["thandi@example.com", "+27 82 555 0101", "(021) 555-0101"])
def test_accepts_email_or_phone_contact(client, contact):
    response = client.post("/api/bookings", json={**VALID, "customer_contact": contact})
    assert response.status_code == 201


def test_trims_whitespace(client):
    response = client.post(
        "/api/bookings",
        json={**VALID, "customer_name": "  Thandi M  ", "customer_contact": " a@b.co "},
    )
    assert response.status_code == 201
    assert response.json()["customer_name"] == "Thandi M"
    assert response.json()["customer_contact"] == "a@b.co"


@pytest.mark.parametrize(
    "field, label",
    [
        ("service_id", "service"),
        ("starts_at", "date and time"),
        ("customer_name", "name"),
        ("customer_contact", "contact"),
    ],
)
@pytest.mark.parametrize("how", ["absent", "null", "blank"])
def test_rejects_missing_required_field(client, field, label, how):
    payload = dict(VALID)
    if how == "absent":
        del payload[field]
    elif how == "null":
        payload[field] = None
    else:
        payload[field] = "   "

    response = client.post("/api/bookings", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == f"Please provide: {label}."
    assert body["errors"] == [{"field": field, "message": "Field required", "missing": True}]
    assert stored_bookings(client) == []


def test_lists_every_missing_field(client):
    response = client.post("/api/bookings", json={})

    assert response.status_code == 422
    assert response.json()["detail"] == "Please provide: service, date and time, name, contact."
    assert stored_bookings(client) == []


def test_rejects_invalid_contact(client):
    response = client.post("/api/bookings", json={**VALID, "customer_contact": "call me"})

    assert response.status_code == 422
    assert response.json()["detail"] == "Enter a valid phone number or email address."
    assert stored_bookings(client) == []


def test_rejects_invalid_date(client):
    response = client.post("/api/bookings", json={**VALID, "starts_at": "next tuesday"})

    assert response.status_code == 422
    assert response.json()["detail"].startswith("Invalid date and time:")
    assert stored_bookings(client) == []


def test_rejects_unknown_service(client):
    response = client.post("/api/bookings", json={**VALID, "service_id": 999})

    assert response.status_code == 422
    assert response.json()["detail"] == "The selected service doesn't exist."
    assert stored_bookings(client) == []


def test_rejects_non_json_body(client):
    response = client.post(
        "/api/bookings", content="not json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Request body must be a JSON object."
    assert stored_bookings(client) == []
