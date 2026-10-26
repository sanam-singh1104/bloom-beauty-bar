from datetime import UTC, datetime

from responder.alerts import select_alerts


def test_selects_firing_booking_alert(payload):
    alerts, skipped = select_alerts(payload)

    assert skipped == []
    [alert] = alerts
    assert alert.name == "Booking creation server errors"
    assert alert.endpoint == "POST /api/bookings"
    assert (alert.method, alert.route) == ("POST", "/api/bookings")
    assert alert.fingerprint == "sample0000000001"
    assert alert.starts_at == datetime(2026, 10, 26, 10, 48, tzinfo=UTC)
    assert alert.window == "5m"
    assert alert.dashboard_url.startswith("http://localhost:3000/d/bloom-bookings")


def test_skips_resolved_and_unknown_alerts(payload):
    booking = payload["alerts"][0]
    resolved = {**booking, "status": "resolved"}
    other = {**booking, "labels": {**booking["labels"], "alertname": "TestAlert"}}
    payload["alerts"] = [resolved, other]

    alerts, skipped = select_alerts(payload)

    assert alerts == []
    assert skipped == [
        "Booking creation server errors: status is 'resolved', not firing",
        "TestAlert: not an alert this responder handles",
    ]


def test_missing_endpoint_label_falls_back_to_known_endpoint(payload):
    del payload["alerts"][0]["labels"]["endpoint"]
    payload["alerts"][0]["startsAt"] = "not a time"

    [alert], _ = select_alerts(payload)

    assert alert.endpoint == "POST /api/bookings"
    assert alert.starts_at.tzinfo is not None


def test_empty_payload():
    assert select_alerts({}) == ([], [])
