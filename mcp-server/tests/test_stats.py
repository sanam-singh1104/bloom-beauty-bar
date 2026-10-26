import json
from datetime import datetime

import stats

NOW = datetime(2026, 11, 3, 12, 0)
SERVICES = {1: "Haircut", 2: "Manicure", 3: "Facial"}
BOOKINGS = [
    (1, datetime(2026, 11, 1, 10, 0)),  # past
    (1, datetime(2026, 11, 3, 15, 30)),  # later today
    (2, datetime(2026, 11, 4, 9, 0)),
    (1, datetime(2026, 11, 4, 11, 0)),
    (2, datetime(2026, 11, 20, 9, 0)),  # beyond the 7-day window
    (9, datetime(2026, 11, 5, 9, 0)),  # service since removed
]

API_BOOKINGS = [
    {
        "id": 1,
        "service_id": 1,
        "starts_at": "2026-11-03T15:30:00",
        "customer_name": "Thandi Mokoena",
        "customer_contact": "thandi.private@example.com",
        "created_at": "2026-10-26T09:00:00",
    }
]
API_SERVICES = [{"id": 1, "name": "Haircut", "duration_minutes": 30, "price_rand": 250}]


def test_summarize_counts_upcoming_by_service_and_day():
    result = stats.summarize(SERVICES, BOOKINGS, NOW)

    assert result == {
        "as_of": "2026-11-03T12:00",
        "total_bookings": 6,
        "upcoming": 5,
        "past": 1,
        "next_booking_at": "2026-11-03T15:30",
        "upcoming_by_service": {"Haircut": 2, "Manicure": 2, "unknown service 9": 1},
        "next_7_days_by_date": {"2026-11-03": 1, "2026-11-04": 2, "2026-11-05": 1},
        "services_with_no_upcoming_bookings": ["Facial"],
    }


def test_summarize_with_no_bookings():
    result = stats.summarize(SERVICES, [], NOW)
    assert result["total_bookings"] == 0
    assert result["next_booking_at"] is None
    assert result["services_with_no_upcoming_bookings"] == ["Facial", "Haircut", "Manicure"]


def test_fetch_keeps_only_service_and_time(monkeypatch):
    responses = {"/api/services": API_SERVICES, "/api/bookings": API_BOOKINGS}
    monkeypatch.setattr(stats, "_get", lambda url, path, timeout: responses[path])

    services, bookings = stats.fetch("http://bloom")

    assert services == {1: "Haircut"}
    assert bookings == [(1, datetime(2026, 11, 3, 15, 30))]
    summary = json.dumps(stats.summarize(services, bookings, NOW))
    assert "Thandi" not in summary
    assert "example.com" not in summary
