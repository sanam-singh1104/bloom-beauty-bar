# Demo: the Agent Extension Pack in action

About 10 minutes. Run everything from the repo root. One-time prep:
`docker compose up --build -d --wait`, the MCP server venv
([mcp-server/README.md](../mcp-server/README.md)), and `BLOOM_MCP_PYTHON` set.

## 1. The agent reads the project instructions
Start `claude` in the repo and ask:

> What's the API for cancelling a booking, and where does validation live?

**Expect:** an answer taken from `AGENTS.md` without searching the code.
`DELETE /api/bookings/{id}` returns `204`, or `404 {"detail": "Booking not
found."}`. Validation is backend-only, with the 422 `{detail, errors}` shape.

## 2. The reusable workflow runs
> Run the checks.

The agent invokes the `run-checks` skill, which runs `py scripts/run_checks.py`.

**Expect:** ruff lint and format for `backend/`, `incident-response/` and
`mcp-server/`, then every test suite, ending in:
```
PASS  ruff lint
PASS  ruff format
PASS  tests
PASS  responder tests
PASS  mcp-server tests
All checks passed.
```

## 3. The subagent reviews a change
[demo/breaking-change.diff](demo/breaking-change.diff) is a proposed change.
It makes cancelling return `200` with a body instead of `204`, and rewords
the 404.

> Use the api-reviewer subagent to review docs/demo/breaking-change.diff.

Or run it headless:
```
claude -p --agent api-reviewer "Review this proposed change: $(cat docs/demo/breaking-change.diff)"
```

**Expect:** `## API review: Breaking`, with file:line findings:
- It contradicts the documented `204` and 404 text in AGENTS.md.
- `test_manage_bookings.py:53,61,66` and `test_booking_journey.py:44` would fail.
- `manage.js:75` only survives by luck (`response.ok`).
- The `Response` import becomes unused.

It uses only Read, Grep and Glob, with no permission prompts and no edits.
A real run took 25s and about $0.17.

## 4. The MCP tool is called
First approval: run `/mcp` and approve **bloom-stats**. Then:

> How many bookings are coming up, and which services have none?

**Expect:** the agent calls `bloom-stats › get_booking_stats` (one call, no
arguments) and answers from aggregates like:
```json
{"total_bookings": 11, "upcoming": 11, "next_booking_at": "2026-10-27T09:40",
 "upcoming_by_service": {"Hair Colour": 4, "Haircut": 4, "Root Touch-Up": 2, "Pedicure": 1},
 "services_with_no_upcoming_bookings": ["Facial", "Manicure"]}
```
The output has no names and no contacts. Asking *"who booked the haircuts?"*
gets no answer from this tool, by design.

## 5. A hook/guardrail fires
> In mcp-server/server.py, raise ToolError when the API can't be reached.
> Add the code first and the import second.

**Expect:** after the first edit the ruff hook blocks with:
```
ruff found problems it couldn't auto-fix in mcp-server/server.py ...
F821 Undefined name `ToolError`
```
The agent sees the blocking error, adds the import, and the next edit passes
cleanly. (This happened for real while building the MCP server.) Any edit
also comes back formatted, because the hook runs `ruff format`.

## 6. (Optional) The custom agent responds to an alert
Hold an SQLite lock so a booking fails:
```
docker compose exec backend python -c "import sqlite3,time; c=sqlite3.connect('/data/bloom.db', isolation_level=None); c.execute('BEGIN EXCLUSIVE'); time.sleep(25); c.execute('ROLLBACK')"
```
While it runs, make a booking. It returns 500 after about 5s. Within about a
minute the Grafana alert fires and the webhook reaches the responder. With a
token set, `curl localhost:8001/incidents` shows the investigation running,
and `report.md` lands in `incident-response/incidents/<id>/`. An example
report:
[issue #9 run](../incident-response/incidents/20261026T112625Z-booking-creation-server-errors-sample00/report.md).
It traced the failures to SQLite's 5s busy timeout.
