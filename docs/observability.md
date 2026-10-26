# Observability

Booking creation (`POST /api/bookings`) is the key user journey. It emits
OpenTelemetry **traces, metrics and logs** that share a trace ID, so one
request can be followed across all three. Code: `backend/app/telemetry.py`.

Where the signals go depends on `TELEMETRY_EXPORTER`:

- **docker compose** (`otlp`): the app sends OTLP/HTTP to an OpenTelemetry
  Collector, which forwards metrics to Prometheus, logs to Loki and traces to
  Tempo. Grafana reads all three and has a provisioned dashboard.
- **Render / plain uvicorn** (`console`, the default): one JSON object per line
  on stdout, visible in the platform's log view.

## Local pipeline (docker compose)

```
backend --OTLP/HTTP--> otel-collector --+--> prometheus  (metrics, OTLP receiver)
                                        +--> loki        (logs, native /otlp)
                                        +--> tempo       (traces, OTLP gRPC)
grafana (http://localhost:3000) reads prometheus, loki, tempo
```

All config is in `observability/`:

| File | What it sets up |
|---|---|
| `otel-collector.yaml` | OTLP receiver, `attributes/scrub` safety-net processor, exporters to the three stores |
| `prometheus.yml` | OTLP ingestion settings (Prometheus runs with `--web.enable-otlp-receiver` and `created-timestamp-zero-ingestion`) |
| `loki.yaml` | Single-process Loki, filesystem storage, 7-day retention |
| `tempo.yaml` | Single-process Tempo, local storage, 7-day retention |
| `grafana/provisioning/datasources/` | Prometheus, Loki, Tempo, with log-to-trace and trace-to-log links |
| `grafana/provisioning/dashboards/` + `grafana/dashboards/bloom-bookings.json` | The **Bloom: Booking requests** dashboard (Grafana's home page) |

Only the app (`:8000`) and Grafana (`127.0.0.1:3000`) are published. Data lives in
the `prometheus-data`, `loki-data`, `tempo-data` and `grafana-data` volumes.

Grafana lets anyone on this machine view dashboards without logging in. To
edit, log in as `admin` with `GRAFANA_ADMIN_PASSWORD` from `.env` (default
`admin` if unset). Provisioned dashboards can't be saved from the UI: edit
`bloom-bookings.json` and run `docker compose restart grafana`.

### Dashboard: Bloom: Booking requests

- **Stats** for the selected range: booking requests, bookings created,
  rejected (422), server errors (5xx), server error rate.
- **Booking requests by status code**: `POST /api/bookings` per interval,
  stacked by status.
- **Booking errors**: 5xx plus rejections by reason (`invalid`, `unknown_service`).
- **Booking request latency**: p50 and p95.
- **Recent booking traces** (Tempo) and **Booking logs** (Loki). A log line's
  `TraceID` link opens its trace. From a span, "Logs for this span" goes back.

### Metric names in Prometheus

OTLP names are translated: `http.server.request.duration` becomes
`http_server_request_duration_seconds_{count,sum,bucket}`, and the counters
become `bloom_bookings_created_total` and `bloom_bookings_rejected_total`.
Attributes become labels (`http_route`, `http_response_status_code`,
`http_request_method`, `reason`). `service.name` becomes `job="bloom-beauty-bar"`.

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
- The Collector's `attributes/scrub` processor is a second line of defence.
  It deletes client addresses, user agents, query strings, HTTP headers,
  exception messages and stack traces, `customer_*` keys, and anything that
  looks like a password, secret, token, cookie or authorization value, on
  every signal before it is stored.

## Configuration

| Variable | Effect |
|---|---|
| `TELEMETRY_EXPORTER` | `console` (default), `otlp` (compose), or `none` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Where `otlp` sends (compose: `http://otel-collector:4318`) |
| `OTEL_METRIC_EXPORT_INTERVAL` | Metric export period in ms (default 60000; compose sets 10000) |
| `GRAFANA_ADMIN_PASSWORD` | Grafana admin password (compose, from `.env`; default `admin`) |
| `OTEL_SERVICE_NAME` / `OTEL_RESOURCE_ATTRIBUTES` | Override the `service.name` (`bloom-beauty-bar`) and other resource attributes |

Tests install in-memory exporters (see `tests/conftest.py`), so test runs
print nothing.

## Inspecting it locally

```
docker compose up --build -d --wait
```

Make a few bookings at http://localhost:8000, including some with a missing
field. Then open http://localhost:3000, which shows the dashboard on the home
page. Metrics arrive about every 10s, and the dashboard refreshes every 10s.

To see raw console output instead, run the app with `TELEMETRY_EXPORTER=console`
(the default outside compose).

## Not done yet (issue #9)
- An alert on booking-creation errors (for example, the 5xx rate on
  `http_route="/api/bookings"`), and the on-call responder agent.
- A hosted telemetry backend for production (Render still logs to the console).
