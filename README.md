# Bloom Beauty Bar

An online booking site for a beauty salon. Customers browse the services
(hair, nails, facials) and book one by choosing a date and time and leaving a
name and phone number or email. Staff use a manage page to see and cancel
bookings. There are no accounts or payments, by design (see the
[spec](product-spec.md)).

**Live:** https://bloom-beauty-bar.onrender.com (staff view:
[/manage.html](https://bloom-beauty-bar.onrender.com/manage.html)). It's on
Render's free tier, so the first request after it's been idle can take
about a minute.

| | |
|---|---|
| Backend | Python, FastAPI, SQLAlchemy (SQLite locally, Postgres in production) |
| Frontend | Plain HTML/CSS/JS, served by the backend |
| Delivery | GitHub Actions CI; Render deploys `main` only after CI passes |
| Observability | OpenTelemetry → Collector → Prometheus / Loki / Tempo → Grafana, with an alert on booking errors |
| Agents | `AGENTS.md`, a run-checks skill, a ruff hook, an API-review subagent, an MCP server and an on-call responder ([the pack](docs/agent-extension-pack.md)) |

## Run it locally

Needs Docker. From the repo root:

```
docker compose up --build -d --wait
```

| What | Where |
|---|---|
| Booking site | http://localhost:8000 |
| Staff view | http://localhost:8000/manage.html |
| Grafana (dashboard + alert) | http://localhost:3000 (view without login; admin/admin to edit) |
| On-call responder | http://localhost:8001/incidents |

Bookings persist in a Docker volume. `docker compose down -v` wipes them,
along with all telemetry. The responder needs `CLAUDE_CODE_OAUTH_TOKEN` in
`.env` (copy [.env.example](.env.example)) to run investigations; everything
else works without it. To run without Docker, see
[AGENTS.md](AGENTS.md#run-and-test).

## Run the tests

```
py -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements-dev.txt
py scripts/run_checks.py
```

(`python3` and `backend/.venv/bin/python` on macOS/Linux.)

This runs ruff lint and format checks plus every test suite: backend unit and
integration, the responder, and the MCP server. CI runs the same checks, adds
Postgres integration tests, and builds the Docker images.

## Docs

| Doc | What's in it |
|---|---|
| [product-spec.md](product-spec.md) | Features, acceptance criteria, non-goals |
| [AGENTS.md](AGENTS.md) | Stack, decisions, layout, API, conventions (start here) |
| [docs/agent-extension-pack.md](docs/agent-extension-pack.md) | The 7 agent pack items and where each lives |
| [docs/demo.md](docs/demo.md) | Demo script: instructions → skill → subagent → MCP tool → hook |
| [docs/permissions.md](docs/permissions.md) | What each agent and tool can and can't access |
| [docs/observability.md](docs/observability.md) | Telemetry, dashboard, alert, privacy rule |
| [incident-response/README.md](incident-response/README.md) | The on-call responder |
| [mcp-server/README.md](mcp-server/README.md) | The `bloom-stats` MCP server |
| [docs/deployment.md](docs/deployment.md), [docs/release-process.md](docs/release-process.md) | Render deploy, CI/CD, rollback |
| [docs/agent-team.md](docs/agent-team.md) | PM / Engineer / QA roles |

Work is tracked in [GitHub issues](https://github.com/sanam-singh1104/bloom-beauty-bar/issues).
