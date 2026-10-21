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
| Frontend      | JavaScript (framework TBD)                                |
| Backend       | Python, FastAPI                                           |
| Database      | TBD; services seeded at startup, bookings stored          |
| Local run     | Docker Compose, one command                               |
| Tests         | Unit + integration (backend and frontend)                 |
| Deployment    | Public URL with CI/CD                                     |
| Observability | Metrics, logs, traces on booking creation; error alert; on-call responder agent |

Record each decision here (and the reason) when it's made.

## Project layout
_To be filled in as the code is created._ Expected shape:

```
backend/     FastAPI app, models, seed data, tests
frontend/    JavaScript UI, tests
docs/        Project docs (see below)
docker-compose.yml
```

## Run and test
_To be filled in as it's built._

- Run locally: `TBD` (target: `docker compose up`)
- Backend tests: `TBD`
- Frontend tests: `TBD`

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
