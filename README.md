# Bloom Beauty Bar

An online booking site for a general beauty salon. Customers browse the salon's
services (hair, nails, and facials), book an appointment by choosing a service,
date, and time and leaving their contact details, and staff use a manage view
to see and cancel bookings.

- **Backend:** Python (FastAPI)
- **Frontend:** JavaScript
- **Database:** SQLite via SQLAlchemy (Postgres-ready); services seeded at startup

See [product-spec.md](product-spec.md) for the full spec, including user
stories, acceptance criteria, and non-goals.

## Run locally

With Docker, from the repo root:

```
docker compose up --build
```

Open http://localhost:8000. Data is stored in SQLite in a Docker volume, so it
survives restarts.

Without Docker, see [AGENTS.md](AGENTS.md#run-and-test).

## Status

Early development: scaffolding and database are done; booking features are
next. See the [issues](https://github.com/sanam-singh1104/bloom-beauty-bar/issues).
