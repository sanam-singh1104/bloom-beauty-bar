# AGENTS.md

Project context for coding agents working on Bloom Beauty Bar. Keep this file
current as the project is built.

## What this is
An online booking site for a general beauty salon. Customers browse a fixed,
seeded menu of services, book one at a date and time with their name and a
contact (phone or email), and staff use a manage view to list and cancel
bookings. No accounts, payments, availability logic, or rescheduling.

**Source of truth:** [product-spec.md](product-spec.md) — features, acceptance
criteria, and non-goals. If a task conflicts with the spec, the spec wins;
flag the conflict rather than guessing.

## Stack
| Area          | Choice                                                    |
|---------------|-----------------------------------------------------------|
| Frontend      | Plain HTML/CSS/JS, no build step; served by FastAPI       |
| Backend       | Python, FastAPI                                           |
| Database      | SQLAlchemy; SQLite by default, Postgres via `DATABASE_URL` |
| Local run     | `docker compose up --build` (SQLite in a named volume)    |
| Tests         | pytest: `tests/unit` + `tests/integration` (SQLite; Postgres in CI) |
| Lint/format   | ruff (`backend/pyproject.toml`), auto-run by an agent hook |
| Deployment    | Render (`render.yaml`), live at https://bloom-beauty-bar.onrender.com |
| CI/CD         | GitHub Actions (`.github/workflows/ci.yml`); Render deploys `main` after checks pass |
| Observability | OpenTelemetry on booking creation; compose: Collector → Prometheus / Loki / Tempo → Grafana ([docs/observability.md](docs/observability.md)); alert + on-call agent still to do |

Record each decision here (and the reason) when it's made.

- **Frontend served by the backend** (`StaticFiles` mounted at `/`), so the
  page calls `/api/...` same-origin with no CORS or second server.
- **Prices stored as whole rand** (`price_rand`), durations as minutes.
- **Swappable storage:** endpoints depend on the `Store` protocol
  (`app/store.py`) via `Depends(get_store)`. `SqlStore` is the only
  implementation; the database is picked by `DATABASE_URL`.
- **Schema via `create_all`**, no migrations yet. Seeding adds missing
  services by name, so it's safe on every startup. Add Alembic if the schema
  starts changing after real data exists.
- **Booking times are naive local (salon) time.**
- **Deployed to Render** via the `render.yaml` Blueprint: one Docker web
  service plus managed Postgres (free plans, `frankfurt`). Chosen because one
  file declares both the app and the database and Render injects the DB URL,
  so no secrets are handled by hand. Bare `postgres(ql)://` URLs are rewritten
  to `postgresql+psycopg://` in `sql_store.normalize_database_url`. See
  [docs/deployment.md](docs/deployment.md).
- **CI on GitHub Actions; Render deploys only after CI passes**
  (`autoDeployTrigger: checksPass`). Chosen over a deploy hook called from the
  workflow: no secret to manage, and the deploy is always the exact commit that
  passed. Integration tests run on SQLite and on Postgres, which is what
  production uses. See [docs/release-process.md](docs/release-process.md).
- **OpenTelemetry SDK set up by hand, console export for now** (`app/telemetry.py`).
  Our own ASGI middleware makes the request span and the
  `http.server.request.duration` metric (route + status code); FastAPI's
  built-in telemetry is turned off because it records client addresses and
  submitted values. **Telemetry must never carry customer data or
  credentials**: open spans with `telemetry.span()` (exception type only, no
  message), and log ids and field names, never names/contacts. See
  [docs/observability.md](docs/observability.md).
- **Local telemetry stack in compose**: the app sends OTLP to an OpenTelemetry
  Collector, which routes metrics to Prometheus (native OTLP receiver), logs
  to Loki (native OTLP) and traces to Tempo. Grafana is provisioned from
  files. Chosen because it's all open source, runs offline, and uses one
  protocol (OTLP) end to end, so a hosted backend later only changes the
  Collector's exporters. The Collector also scrubs PII-shaped attributes as a
  safety net. Image versions are pinned in `docker-compose.yml`.

## Project layout
```
backend/
  app/main.py        FastAPI app: API routes under /api, serves frontend/ at /
  app/models.py      Pydantic models (Service, BookingCreate, Booking)
  app/store.py       Store protocol + seed service list
  app/sql_store.py   SQLAlchemy Store (tables, seeding, queries)
  app/errors.py      Validation errors -> {"detail", "errors"} 422 responses
  app/telemetry.py   OpenTelemetry setup, request middleware, safe span helper
  tests/unit/        No app, no DB: validation rules, error messages, seed data
  tests/integration/ HTTP API + store against a fresh SQLite file per test,
                     incl. the full browse -> book -> list -> cancel journey
  pyproject.toml     pytest markers + ruff config
  Dockerfile         built from repo root (copies frontend/ too); listens on $PORT (default 8000)
  requirements.txt / requirements-dev.txt
frontend/
  index.html + app.js      Customer page: services list + booking form
  manage.html + manage.js  Staff page: all bookings, cancel button (no auth;
                           accounts are a non-goal)
  common.js                Shared helpers (API_BASE, getJson, formatWhen);
                           load it before the page script
  styles.css
docker-compose.yml   backend + `bloom-data` volume holding the SQLite DB, plus the
                     telemetry stack (otel-collector, prometheus, loki, tempo, grafana)
observability/       Collector, Prometheus, Loki, Tempo config + Grafana
                     datasources and the booking dashboard (provisioned)
render.yaml          Render Blueprint: web service + Postgres (docs/deployment.md)
.github/workflows/ci.yml  CI: lint, format, JS syntax, unit + integration tests
                     (SQLite and Postgres), Docker build + smoke test
scripts/run_checks.py  Lint + format check + all tests in one command
agent-hooks/         ruff-on-edit Claude Code hook + optional git pre-commit
.claude/             settings.json (registers the hook), skills/run-checks
docs/                Project docs (see below)
```

## API
- `GET /api/health` → `{"status": "ok"}`
- `GET /api/services` → list of `{id, name, duration_minutes, price_rand}`
- `POST /api/bookings` with `{service_id, starts_at, customer_name, customer_contact}`
  (`starts_at` like `2026-11-03T10:30`) → `201` with the saved booking
  (`id`, `created_at` added).
- `GET /api/bookings` → every booking, soonest `starts_at` first.
- `DELETE /api/bookings/{id}` → `204`; `404 {"detail": "Booking not found."}`
  if it doesn't exist (or was already cancelled).

Errors use one shape everywhere: `422` with
`{"detail": "<one line for people>", "errors": [{field, message, missing}]}`.
Absent, `null`, and blank values count as missing, e.g.
`"Please provide: date and time, contact."`. Contact must look like a phone
number (7–15 digits) or an email. An unknown `service_id` gets a 422 too.

## Configuration
- `DATABASE_URL`: SQLAlchemy URL. Default (local dev): a SQLite file at
  `backend/data/bloom.db`. Compose uses `sqlite:////data/bloom.db`.
  For Postgres: `postgresql+psycopg://user:pass@host:5432/db` (psycopg is
  installed; plain `postgresql://` / `postgres://` URLs are converted). See
  the commented `db` service in `docker-compose.yml`.
- `TEST_DATABASE_URL` (tests only): run integration tests against this
  database instead of a temp SQLite file. It is wiped before and after every
  test, so never point it at real data. CI sets it to a Postgres service container.
- `TELEMETRY_EXPORTER`: `console` (default), `otlp` (to `OTEL_EXPORTER_OTLP_ENDPOINT`;
  compose uses this), or `none`. `OTEL_METRIC_EXPORT_INTERVAL` sets the metric
  period in ms (compose: 10000).
- `GRAFANA_ADMIN_PASSWORD` (compose, via `.env`): Grafana admin password, default `admin`.
- `PORT`: port uvicorn listens on in the Docker image (default 8000; Render
  sets it).

## Run and test
Everything, from the repo root:
```
docker compose up --build
```
Open http://localhost:8000 (app) and http://localhost:3000 (Grafana). Data persists in the `bloom-data` volume;
`docker compose down -v` wipes it.

Without Docker, from `backend/` (Windows shown; on macOS/Linux use `python3`
and `.venv/bin/python`):
```
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m uvicorn app.main:app --reload
```

**All checks (lint + format + every test), from the repo root:**
```
py scripts/run_checks.py            # add --fix, --unit, --integration, or -- <pytest args>
```
This is the `run-checks` skill (`.claude/skills/run-checks/`); run it before
committing or closing an issue. Tests only: `pytest` from `backend/`
(`-m unit` or `-m integration` to narrow).

Python files are ruff-fixed and formatted automatically after every agent
edit; leftover problems come back as a blocking hook error. See
[agent-hooks/README.md](agent-hooks/README.md).

## Conventions
- Services come from the database, never hardcoded in the frontend.
- Booking validation lives in the backend; reject missing service, date/time,
  name, or contact with a clear message. The frontend may also validate, but
  the backend is authoritative.
- Every feature needs tests that cover its acceptance criteria: unit tests
  for logic, an integration test for the behaviour over HTTP.
- `py scripts/run_checks.py` must pass before a task is handed to QA.
- Don't build anything listed under non-goals in the spec.
- Never commit secrets; use `.env` (gitignored) and keep `.env.example` current.
- Small, focused commits with clear messages.

## Docs
- [product-spec.md](product-spec.md) — what to build
- [docs/agent-team.md](docs/agent-team.md) — PM / Engineer / QA roles and the
  task workflow
- [docs/deployment.md](docs/deployment.md) — deploying to Render
- [docs/release-process.md](docs/release-process.md) — push → CI → deploy →
  live, and rollback
- [docs/observability.md](docs/observability.md) — traces, metrics, logs, and
  the no-customer-data rule
- [.claude/skills/run-checks/SKILL.md](.claude/skills/run-checks/SKILL.md) —
  the run-checks procedure
- [agent-hooks/README.md](agent-hooks/README.md) — the ruff hook and the
  optional git pre-commit hook
