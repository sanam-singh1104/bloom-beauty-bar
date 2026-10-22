# Bloom Beauty Bar

An online booking site for a general beauty salon. Customers browse the salon's
services (hair, nails, and facials), book an appointment by choosing a service,
date, and time and leaving their contact details, and staff use a manage view
to see and cancel bookings.

- **Backend:** Python (FastAPI)
- **Frontend:** JavaScript
- **Database:** services are seeded at startup; bookings are stored, listed, and deleted

See [product-spec.md](product-spec.md) for the full spec, including user
stories, acceptance criteria, and non-goals.

## Run locally

Requires Python 3.11+. From `backend/` (Windows shown; on macOS/Linux use
`python3` and `.venv/bin/python`):

```
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --reload
```

Open http://localhost:8000. Run tests with `.venv\Scripts\python -m pytest`.

## Status

Early development. Data is held in memory for now; a real database and
Docker Compose come next. See [AGENTS.md](AGENTS.md) for details.
