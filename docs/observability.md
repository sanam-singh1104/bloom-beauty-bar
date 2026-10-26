# Observability

Booking creation (`POST /api/bookings`) is the key user journey. It emits
OpenTelemetry **traces, metrics and logs** that share a trace ID, so one
request can be followed across all three. Code: `backend/app/telemetry.py`.

For now every signal is printed to the console, one JSON object per line, so
`docker compose logs` (and Render's log view) shows it. No external telemetry
backend is set up yet.

## What is emitted

**Traces**
- One `SERVER` span per HTTP request, named `<METHOD> <route>`, e.g.
  `POST /api/bookings`. Attributes: `http.request.method`, `http.route`
  (the route template, e.g. `/api/bookings/{booking_id}`, never the raw path),
  `http.response.status_code`, and `error.type` on unhandled exceptions.
- A child `create_booking` span with `booking.service_id` and, once saved,
  `booking.id`.

**Metrics**
- `http.server.request.duration` (histogram, seconds): every request, with
  `http.request.method`, `http.route`, `http.response.status_code`. Its count
  is the request count, so it also gives the error rate per route and status.
- `bloom.bookings.created` (counter), by `booking.service_id`.
- `bloom.bookings.rejected` (counter), by `reason`: `invalid` (missing or bad
  fields) or `unknown_service`.

**Logs** (logger `bloom`)
- `Booking created: id=<id> service_id=<id>` (INFO)
- `Booking rejected: <reason> (<field names>)` (WARN)
- `Unhandled error: <ExceptionType>` (ERROR)

Each log record carries the `trace_id` and `span_id` of the span it was
written in.

## Privacy rule

Telemetry never carries customer data or credentials. Only ids, routes,
status codes, field **names** and exception **types** are recorded. Never
names, contacts, request bodies, headers, query strings, client addresses, or
exception messages (a database error can echo the inserted values).

How that's enforced:
- FastAPI's built-in telemetry is turned off (`FastAPI(telemetry=...)` in
  `main.py`). It records client addresses, user agents, and validation errors
  with the submitted values.
- Spans are opened with `telemetry.span()`, which on an exception adds only
  `error.type`. OpenTelemetry's default would add the message and stack trace.
- `tests/integration/test_telemetry.py` submits a booking with a known name
  and contact, and fails if either shows up in any exported span, metric or log.

## Configuration

| Variable | Effect |
|---|---|
| `TELEMETRY_EXPORTER` | `console` (default) or `none` to emit nothing |
| `OTEL_METRIC_EXPORT_INTERVAL` | Metric export period in ms (default 60000; compose sets 10000) |
| `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES` | Override the `service.name` (`bloom-beauty-bar`) and other resource attributes |

Tests install in-memory exporters (see `tests/conftest.py`), so test runs
print nothing.

## Inspecting it locally

```
docker compose up --build -d
# book something at http://localhost:8000, then:
docker compose logs backend | grep '"Booking created'       # the log line; note its trace_id
docker compose logs backend | grep <trace_id>               # its log + both spans
docker compose logs backend | grep '"http.server.request.duration"'   # metrics (every 10s)
```

Spans and logs are batched, so they appear a few seconds after the request.

## Not done yet (issue #9)
- Exporting to a real telemetry backend.
- An alert on booking-creation errors (`http.route=/api/bookings` with
  status 5xx, or `error.type` on the span), and the on-call responder agent.
