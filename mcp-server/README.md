# bloom-stats MCP server

A small MCP server that gives an agent **one read-only tool** instead of
access to the database or the full API.

| Tool | Returns |
|---|---|
| `get_booking_stats` | Total, upcoming and past bookings; the next booking time; upcoming bookings per service; bookings per day for the next 7 days; services with no upcoming bookings |

## How it stays scoped
- **One tool, no arguments.** Nothing to inject, no queries, no writes. It's
  annotated `readOnlyHint: true`, `destructiveHint: false`.
- **Aggregates only.** It reads `GET /api/services` and `GET /api/bookings`,
  keeps just `service_id` and `starts_at`, and drops names and contacts at
  parse time (`stats.fetch`). A test checks they never reach the output.
- **No credentials, no DB.** It talks to the app's HTTP API
  (`BLOOM_API_URL`, default `http://localhost:8000`), the same one the
  manage page uses. It has no `DATABASE_URL` and no `.env`.
- **Approval first.** Claude Code asks you to approve a project MCP server
  (from `.mcp.json`) before it's ever started.

## Set up (once)

From the repo root:

```
py -m venv mcp-server/.venv                                    # macOS/Linux: python3 -m venv ...
mcp-server/.venv/Scripts/python -m pip install -r mcp-server/requirements.txt   # .venv/bin/python on macOS/Linux
```

`.mcp.json` (repo root) registers the server as `bloom-stats`. It runs
`${BLOOM_MCP_PYTHON:-python3} mcp-server/server.py`, so point
`BLOOM_MCP_PYTHON` at the venv's Python before starting Claude Code:

```
# PowerShell
$env:BLOOM_MCP_PYTHON = "$PWD\mcp-server\.venv\Scripts\python.exe"
# bash / zsh
export BLOOM_MCP_PYTHON="$PWD/mcp-server/.venv/bin/python"
```

Then start the app (`docker compose up -d backend`) and run `claude` in the
repo. Approve **bloom-stats** when asked (or later via `/mcp`), and ask
something like *"How many bookings are coming up, by service?"*.
`claude mcp list` shows its status.

To read the live site instead, set
`BLOOM_API_URL=https://bloom-beauty-bar.onrender.com`.

## Files
- `server.py`: the MCP server (stdio), with one tool
- `stats.py`: fetch and aggregate (stdlib only; no MCP needed)
- `tests/`: aggregation and privacy tests, plus protocol tests through an
  in-process MCP client (skipped if `mcp` isn't installed)

Run the tests with `mcp-server/.venv/Scripts/python -m pytest mcp-server`, or
as part of `py scripts/run_checks.py`.
