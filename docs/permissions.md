# Agent permissions and security

What each agent, tool and guardrail in this repo can and can't do. The rule
throughout: **give each agent the least it needs**. No agent gets `.env`,
customer data, or write access it doesn't need.

## Summary

| Piece | Can | Can't |
|---|---|---|
| Coding agent (Claude Code in the repo) | Read/edit code, run commands, under your permission mode | Skip the ruff hook; start MCP servers you haven't approved |
| `api-reviewer` subagent | Read, Grep, Glob | Edit, write, run commands, use the web or MCP |
| `bloom-stats` MCP server | One tool: aggregate booking counts via the public API | Return names or contacts; write; query the DB; read `.env` |
| On-call responder (`incident-response/`) | Query Prometheus/Loki/Tempo; run Claude Code with Read/Grep/Glob on a read-only source mount | See `.env` or `backend/data`; edit files; run commands; browse |
| Ruff hook | Format and fix Python after each edit; block on unfixable issues | Change non-Python files |

## Details

### Coding agent
- Instructions come from `AGENTS.md`. The spec wins on conflicts.
- **Guardrail:** `.claude/settings.json` runs `agent-hooks/ruff-on-edit.sh`
  after every Write/Edit. It formats the file, applies safe fixes, and returns
  anything left over as a **blocking** error the agent must fix. See
  [agent-hooks/README.md](../agent-hooks/README.md).
- Project MCP servers in `.mcp.json` need your approval before they run.

### `api-reviewer` subagent ([.claude/agents/api-reviewer.md](../.claude/agents/api-reviewer.md))
- `tools: Read, Grep, Glob`. No Bash means no `git`, so the caller passes
  the diff.
- Scoped to the API contract (routes, models, the error shape, the AGENTS.md
  API section) and its consumers. It reports and never edits.

### `bloom-stats` MCP server ([mcp-server/](../mcp-server/README.md))
- Exactly one tool, `get_booking_stats`, with no arguments and a
  `readOnlyHint`.
- Reads the public HTTP API; it has no database URL and no secrets.
- Drops `customer_name` and `customer_contact` when it parses the response.
  Tests check they never reach the output.
- The agent gets "4 haircuts this week", not the booking list. This is the
  point: a scoped tool instead of broad access.

### On-call responder ([incident-response/](../incident-response/README.md))
- **Read-only session:** Claude Code runs with `--tools Read,Grep,Glob`,
  `--permission-mode dontAsk` (anything else is denied, not prompted),
  `--strict-mcp-config` (no MCP servers) and `--no-session-persistence`.
- **Limited workspace:** only these paths are mounted, read-only, at
  `/workspace`: `backend/app`, `backend/tests`, `frontend`, `observability`,
  `docs`, `AGENTS.md`, `product-spec.md` and `docker-compose.yml`. It never
  sees `.env` (holds the token) or `backend/data` (bookings).
- **Token:** `CLAUDE_CODE_OAUTH_TOKEN` comes from `.env` (gitignored). Only
  the `claude` process gets it, through a minimal environment. It's never
  logged, and it's masked if the CLI echoes it.
- **Prompt:** contains telemetry only, which has no customer data (next
  section). The prompt tells Claude to treat it as data, not instructions.
- **Limits:** one investigation at a time, a 15-minute timeout, and a
  30-minute cooldown per alert. Port 8001 is bound to 127.0.0.1.

### Telemetry (what agents can see about customers)
- The app records ids, routes, status codes, field *names* and exception
  *types*. It never records names, contacts, bodies, headers, client IPs or
  exception messages.
- FastAPI's built-in telemetry is off because it would record those.
- The OTel Collector scrubs PII-shaped attributes as a second line of
  defence. See [observability.md](observability.md#privacy-rule).

### Secrets
- `.env` is gitignored, and `.env.example` documents the variables. The
  only secret today is the responder's token; Grafana's password defaults to
  `admin` for local use.
- Incident folders are gitignored. Committing one means `git add -f`, after
  checking it for secrets and customer data.

## Known gaps
- The manage page and `GET /api/bookings` have no auth (accounts are a spec
  non-goal). The MCP server deliberately exposes less than that endpoint
  does.
- Grafana allows anonymous viewing on localhost. The telemetry stack and the
  responder are local only; production on Render logs to the console.
