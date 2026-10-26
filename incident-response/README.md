# On-call responder

Grafana sends firing alerts to `POST /alerts` (port 8001). For a booking 5xx
alert ("Booking creation server errors"), the responder:

1. Gathers context for the alert's endpoint, from 15 minutes before it fired
   until now:
   - request counts by status code (Prometheus)
   - ERROR/WARN log lines (Loki)
   - traces of the failed requests, plus any trace an error log points at
     (Tempo, up to 5)
2. Writes that context into a prompt and runs **Claude Code headless**
   (`claude --print`) in a read-only workspace of the source code. The
   session asks for a ranked root cause with file:line evidence, the impact,
   a mitigation and fix, and next steps.
3. Saves everything to `incidents/<id>/`.

Other alerts, and resolved notifications, are acknowledged (202) and ignored.

## Setup

1. Create a long-lived token: `claude setup-token` (needs a Claude
   subscription; it prints a token once).
2. Put it in `.env` at the repo root (gitignored; see `.env.example`):
   ```
   CLAUDE_CODE_OAUTH_TOKEN=<token>
   ```
3. Start or recreate the responder: `docker compose up --build -d --wait`
   (or just `docker compose up -d incident-responder`).
4. Check that it sees the token: `curl localhost:8001/health` should show
   `"token_configured": true`.

Without a token the responder still gathers context and writes the prompt.
It marks the incident `skipped` instead of investigating.

## Send a test alert

```
# Gather context and write the prompt, but don't launch Claude Code:
curl -X POST "localhost:8001/alerts?dry_run=true" -H "content-type: application/json" --data-binary @incident-response/sample-alert.json

# Full run (uses your Claude subscription; takes a minute or more):
curl -X POST localhost:8001/alerts -H "content-type: application/json" --data-binary @incident-response/sample-alert.json
```

The same fingerprint isn't investigated twice within 30 minutes. Re-sending
`sample-alert.json` is refused until then, unless you change its
`fingerprint` or restart the responder. Dry runs are never refused.

To test the whole path from a real failure through Grafana, see "Test it"
under the alert in `docs/observability.md`.

## Results

```
curl localhost:8001/incidents          # newest first, with state
curl localhost:8001/incidents/<id>     # status + report
docker compose logs -f incident-responder
```

Each `incidents/<id>/` folder (gitignored) holds `alert.json` (Grafana's
alert), `context.json` (the gathered telemetry), `prompt.md`, `report.md`,
`claude-output.json` (cost, turns, session) and `status.json`.

States go `received` → `gathering` → `queued` → `investigating` → `done`.
Other outcomes are `failed` (the reason is in status/report), `skipped` (no
token) or `dry_run`.

## Safety

- **Read-only session:** only the `Read`, `Grep` and `Glob` tools exist
  (`--tools`), and anything else is denied rather than prompted
  (`--permission-mode dontAsk`). There are no MCP servers and no session
  persistence. It can't edit files, run commands or browse.
- **Limited workspace:** the source mounted at `/workspace` is specific
  directories only, read-only: `backend/app`, `backend/tests`, `frontend`,
  `observability`, `docs`, plus `AGENTS.md`, `product-spec.md` and
  `docker-compose.yml`. There's no `.env` (the token) and no `backend/data`
  (bookings).
- **No customer data in the prompt:** the telemetry it carries has none (see
  docs/observability.md), and the prompt tells Claude to treat it as data,
  not instructions.
- **Token handling:** the token is passed only to the `claude` process, not
  logged, and masked if the CLI echoes it.
- **Limits:** one investigation at a time, a 15-minute timeout
  (`RESPONDER_TIMEOUT_SECONDS`), and a 30-minute cooldown per alert
  (`RESPONDER_COOLDOWN_MINUTES`).
- **Port binding:** port 8001 is bound to 127.0.0.1 only. Grafana reaches it
  on the compose network.

## Configuration

| Variable | Default |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | unset: gather only, no investigation |
| `RESPONDER_CLAUDE_MODEL` | Claude Code's default model |
| `RESPONDER_TIMEOUT_SECONDS` | `900` |
| `RESPONDER_COOLDOWN_MINUTES` | `30` |
| `PROMETHEUS_URL` / `LOKI_URL` / `TEMPO_URL` | the compose service URLs |

Tests: `pytest` from this folder, or `py scripts/run_checks.py` from the repo root.
