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

## Planned stack
| Area          | Choice                                                    |
|---------------|-----------------------------------------------------------|
| Frontend      | Plain HTML/CSS/JS, no build step; served by FastAPI       |
| Backend       | Python, FastAPI                                           |
| Database      | In-memory store for now (`backend/app/store.py`); real DB in #6 |
| Local run     | Docker Compose, one command                               |
| Tests         | Unit + integration (backend and frontend)                 |
| Deployment    | Public URL with CI/CD                                     |
| Observability | Metrics, logs, traces on booking creation; error alert; on-call responder agent |

Record each decision here (and the reason) when it's made.

- **Frontend served by the backend** (`StaticFiles` mounted at `/`), so the
  page calls `/api/...` same-origin with no CORS or second server.
- **Prices stored as whole rand** (`price_rand`), durations as minutes.

## Project layout
```
backend/
  app/main.py      FastAPI app: API routes under /api, serves frontend/ at /
  app/models.py    Pydantic models
  app/store.py     In-memory store + seed services (replaced in #6)
  tests/           pytest tests
  requirements.txt
frontend/
  index.html, styles.css, app.js   Plain JS, calls /api
docs/              Project docs (see below)
```

## API
- `GET /api/health` → `{"status": "ok"}`
- `GET /api/services` → list of `{id, name, duration_minutes, price_rand}`

## Run and test
From `backend/` (Windows shown; on macOS/Linux use `python3` and
`.venv/bin/python`):

```
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --reload
```
Open http://localhost:8000. Tests: `.venv\Scripts\python -m pytest`.

Docker Compose (`docker compose up`) arrives with issue #6.

## Conventions
- Services come from the database, never hardcoded in the frontend.
- Booking validation lives in the backend; reject missing service, date/time,
  name, or contact with a clear message. The frontend may also validate, but
  the backend is authoritative.
- Every feature needs tests that cover its acceptance criteria.
- Don't build anything listed under non-goals in the spec.
- Never commit secrets; use `.env` (gitignored) and keep `.env.example` current.
- Small, focused commits with clear messages.

## Docs
- [product-spec.md](product-spec.md) — what to build
- [docs/agent-team.md](docs/agent-team.md) — PM / Engineer / QA roles and the
  task workflow
