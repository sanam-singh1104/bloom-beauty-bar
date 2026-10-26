"""Booking stats from the Bloom API: aggregate counts only, never who booked.

Reads GET /api/services and GET /api/bookings (the same public API the
manage page uses). Customer names and contacts are dropped as soon as the
response is parsed; only service ids and times are kept.
"""

import json
import urllib.request
from collections import Counter
from datetime import datetime, timedelta

UPCOMING_DAYS = 7


def _get(api_url: str, path: str, timeout: float) -> list:
    with urllib.request.urlopen(f"{api_url.rstrip('/')}{path}", timeout=timeout) as response:
        return json.load(response)


def fetch(api_url: str, timeout: float = 10) -> tuple[dict[int, str], list[tuple[int, datetime]]]:
    """Service names by id, and (service_id, starts_at) for every booking."""
    services = {s["id"]: s["name"] for s in _get(api_url, "/api/services", timeout)}
    bookings = [
        (b["service_id"], datetime.fromisoformat(b["starts_at"]))
        for b in _get(api_url, "/api/bookings", timeout)
    ]
    return services, bookings


def summarize(
    services: dict[int, str], bookings: list[tuple[int, datetime]], now: datetime
) -> dict:
    """Totals, upcoming bookings per service and per day for the next week."""
    upcoming = sorted(starts for _, starts in bookings if starts >= now)
    week_end = now + timedelta(days=UPCOMING_DAYS)
    per_day = Counter(s.date().isoformat() for s in upcoming if s < week_end)
    per_service = Counter(
        services.get(service_id, f"unknown service {service_id}")
        for service_id, starts in bookings
        if starts >= now
    )
    return {
        "as_of": now.isoformat(timespec="minutes"),
        "total_bookings": len(bookings),
        "upcoming": len(upcoming),
        "past": len(bookings) - len(upcoming),
        "next_booking_at": upcoming[0].isoformat(timespec="minutes") if upcoming else None,
        "upcoming_by_service": dict(per_service.most_common()),
        f"next_{UPCOMING_DAYS}_days_by_date": dict(sorted(per_day.items())),
        "services_with_no_upcoming_bookings": sorted(
            name for name in services.values() if name not in per_service
        ),
    }
