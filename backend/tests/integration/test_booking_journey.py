"""End-to-end journey over HTTP against a real (SQLite file) database:
browse services -> book -> staff list -> cancel, plus data surviving a restart.
"""

from fastapi.testclient import TestClient

from app.main import app


def test_browse_book_list_cancel(client):
    # Browse: customer sees the seeded menu.
    services = client.get("/api/services").json()
    manicure = next(s for s in services if s["name"] == "Manicure")
    assert (manicure["duration_minutes"], manicure["price_rand"]) == (45, 200)

    # Book: a missing field is rejected and nothing is saved...
    rejected = client.post("/api/bookings", json={"service_id": manicure["id"]})
    assert rejected.status_code == 422
    assert rejected.json()["detail"] == "Please provide: date and time, name, contact."
    assert client.get("/api/bookings").json() == []

    # ...and a complete one is saved and returned.
    created = client.post(
        "/api/bookings",
        json={
            "service_id": manicure["id"],
            "starts_at": "2026-11-10T09:15",
            "customer_name": "Lerato K",
            "customer_contact": "lerato@example.com",
        },
    )
    assert created.status_code == 201
    booking = created.json()

    # List: staff see it with service, date/time, name, and contact.
    [listed] = client.get("/api/bookings").json()
    assert listed == booking
    assert listed["service_id"] == manicure["id"]
    assert listed["starts_at"] == "2026-11-10T09:15:00"
    assert listed["customer_name"] == "Lerato K"
    assert listed["customer_contact"] == "lerato@example.com"

    # Cancel: it's removed and no longer listed.
    assert client.delete(f"/api/bookings/{booking['id']}").status_code == 204
    assert client.get("/api/bookings").json() == []


def test_bookings_survive_app_restart(database_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", database_url)
    payload = {
        "service_id": 1,
        "starts_at": "2026-11-03T10:30",
        "customer_name": "Thandi M",
        "customer_contact": "082 555 0101",
    }

    with TestClient(app) as first_run:
        booking = first_run.post("/api/bookings", json=payload).json()

    with TestClient(app) as second_run:
        assert second_run.get("/api/bookings").json() == [booking]
        # Seeding on the second startup didn't duplicate the menu.
        assert len(second_run.get("/api/services").json()) == 6
