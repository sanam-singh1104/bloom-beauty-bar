def book(client, **overrides):
    payload = {
        "service_id": 1,
        "starts_at": "2026-11-03T10:30",
        "customer_name": "Thandi M",
        "customer_contact": "082 555 0101",
        **overrides,
    }
    response = client.post("/api/bookings", json=payload)
    assert response.status_code == 201
    return response.json()


def test_list_is_empty_initially(client):
    response = client.get("/api/bookings")
    assert response.status_code == 200
    assert response.json() == []


def test_list_shows_every_booking_with_details(client):
    later = book(client, service_id=5, starts_at="2026-11-04T15:00",
                 customer_name="Lerato K", customer_contact="lerato@example.com")
    earlier = book(client)

    response = client.get("/api/bookings")

    assert response.status_code == 200
    bookings = response.json()
    # Every booking, soonest first.
    assert [b["id"] for b in bookings] == [earlier["id"], later["id"]]
    assert bookings[1] == later
    assert {k: bookings[1][k] for k in
            ("service_id", "starts_at", "customer_name", "customer_contact")} == {
        "service_id": 5,
        "starts_at": "2026-11-04T15:00:00",
        "customer_name": "Lerato K",
        "customer_contact": "lerato@example.com",
    }


def test_cancel_removes_booking_from_list(client):
    keep = book(client, customer_name="Keep Me")
    cancel = book(client, customer_name="Cancel Me")

    response = client.delete(f"/api/bookings/{cancel['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert [b["id"] for b in client.get("/api/bookings").json()] == [keep["id"]]


def test_cancel_unknown_booking_is_404(client):
    response = client.delete("/api/bookings/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Booking not found."}


def test_cancel_twice_is_404(client):
    booking = book(client)
    assert client.delete(f"/api/bookings/{booking['id']}").status_code == 204
    assert client.delete(f"/api/bookings/{booking['id']}").status_code == 404


def test_manage_page_is_served(client):
    response = client.get("/manage.html")
    assert response.status_code == 200
    assert "Manage bookings" in response.text
