"""Booking creation emits a trace, metrics and logs that share a trace ID,
and none of them carry customer data."""

from fastapi.testclient import TestClient
from opentelemetry.trace import SpanKind, StatusCode

VALID = {
    "service_id": 1,
    "starts_at": "2026-11-03T10:30",
    "customer_name": "Thandi Mokoena",
    "customer_contact": "thandi.private@example.com",
}


def server_span(spans, route):
    [span] = [s for s in spans if s.kind == SpanKind.SERVER and s.attributes["http.route"] == route]
    return span


def request_points(reader):
    """Data points of the request-duration histogram, as attribute dicts."""
    points = []
    for resource_metrics in reader.get_metrics_data().resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                if metric.name == "http.server.request.duration":
                    points += [dict(p.attributes) for p in metric.data.data_points]
    return points


def counter_total(reader, name, **attributes):
    total = 0
    for resource_metrics in reader.get_metrics_data().resource_metrics:
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                if metric.name == name:
                    total += sum(
                        p.value
                        for p in metric.data.data_points
                        if attributes.items() <= dict(p.attributes).items()
                    )
    return total


def test_booking_creation_signals_share_one_trace(client, captured_telemetry):
    response = client.post("/api/bookings", json=VALID)
    assert response.status_code == 201
    booking_id = response.json()["id"]

    spans = captured_telemetry.spans.get_finished_spans()
    server = server_span(spans, "/api/bookings")
    assert server.name == "POST /api/bookings"
    assert server.attributes["http.request.method"] == "POST"
    assert server.attributes["http.response.status_code"] == 201

    [inner] = [s for s in spans if s.name == "create_booking"]
    assert inner.context.trace_id == server.context.trace_id
    assert inner.parent.span_id == server.context.span_id
    assert inner.attributes["booking.id"] == booking_id
    assert inner.attributes["booking.service_id"] == 1

    [log] = [
        r
        for r in captured_telemetry.logs.get_finished_logs()
        if r.log_record.body.startswith("Booking created")
    ]
    assert log.log_record.trace_id == server.context.trace_id
    assert log.log_record.span_id == inner.context.span_id
    assert log.log_record.attributes["booking.id"] == booking_id


def test_request_metric_has_route_and_status_code(client, captured_telemetry):
    created_before = counter_total(captured_telemetry.metrics, "bloom.bookings.created")

    client.post("/api/bookings", json=VALID)
    client.delete("/api/bookings/999999")

    points = request_points(captured_telemetry.metrics)
    assert {
        "http.request.method": "POST",
        "http.route": "/api/bookings",
        "http.response.status_code": 201,
    } in points
    assert {
        "http.request.method": "DELETE",
        "http.route": "/api/bookings/{booking_id}",
        "http.response.status_code": 404,
    } in points
    assert counter_total(captured_telemetry.metrics, "bloom.bookings.created") == created_before + 1


def test_rejected_bookings_are_counted_and_logged(client, captured_telemetry):
    def rejected(reason):
        return counter_total(captured_telemetry.metrics, "bloom.bookings.rejected", reason=reason)

    invalid_before, unknown_before = rejected("invalid"), rejected("unknown_service")

    assert client.post("/api/bookings", json={**VALID, "customer_contact": ""}).status_code == 422
    assert client.post("/api/bookings", json={**VALID, "service_id": 9999}).status_code == 422

    assert rejected("invalid") == invalid_before + 1
    assert rejected("unknown_service") == unknown_before + 1
    assert {
        "http.request.method": "POST",
        "http.route": "/api/bookings",
        "http.response.status_code": 422,
    } in request_points(captured_telemetry.metrics)

    bodies = [r.log_record.body for r in captured_telemetry.logs.get_finished_logs()]
    assert "Booking rejected: invalid (customer_contact)" in bodies
    assert "Booking rejected: unknown_service (service_id)" in bodies


def test_no_customer_data_in_any_signal(client, captured_telemetry):
    client.post("/api/bookings", json=VALID)
    client.post("/api/bookings", json={**VALID, "starts_at": "not a date"})
    client.post("/api/bookings", json={**VALID, "service_id": 9999})
    client.get("/api/bookings")

    exported = "\n".join(
        [s.to_json() for s in captured_telemetry.spans.get_finished_spans()]
        + [r.to_json() for r in captured_telemetry.logs.get_finished_logs()]
        + [captured_telemetry.metrics.get_metrics_data().to_json()]
    )
    assert exported  # sanity: something was captured
    for secret in ("Thandi", "Mokoena", "thandi.private", "example.com", "not a date"):
        assert secret not in exported
    # No client addresses either.
    assert "client.address" not in exported


def test_unhandled_error_is_recorded_without_its_message(client, captured_telemetry, monkeypatch):
    def failing_create(booking):
        # Database errors can echo the inserted values, like this.
        raise RuntimeError(f"insert failed: {booking.customer_name}, {booking.customer_contact}")

    monkeypatch.setattr(client.app.state.store, "create_booking", failing_create)
    client_500 = TestClient(client.app, raise_server_exceptions=False)

    assert client_500.post("/api/bookings", json=VALID).status_code == 500

    server = server_span(captured_telemetry.spans.get_finished_spans(), "/api/bookings")
    assert server.attributes["http.response.status_code"] == 500
    assert server.attributes["error.type"] == "RuntimeError"
    assert server.status.status_code == StatusCode.ERROR
    assert {
        "http.request.method": "POST",
        "http.route": "/api/bookings",
        "http.response.status_code": 500,
    } in request_points(captured_telemetry.metrics)

    logs = captured_telemetry.logs.get_finished_logs()
    assert "Unhandled error: RuntimeError" in [r.log_record.body for r in logs]
    exported = "\n".join(
        [s.to_json() for s in captured_telemetry.spans.get_finished_spans()]
        + [r.to_json() for r in logs]
    )
    assert "Thandi" not in exported
    assert "thandi.private" not in exported
