# Agent Extension Pack

The seven pieces that shape how coding agents work on Bloom Beauty Bar.
Demo: [demo.md](demo.md). Security: [permissions.md](permissions.md).

| # | Item | What it does | Where |
|---|---|---|---|
| 1 | **Project instructions** | Stack, decisions, layout, API, conventions; the agent reads it first | [AGENTS.md](../AGENTS.md) |
| 2 | **Reusable workflow (skill)** | `run-checks`: ruff lint + format + every test suite in one command, then fix what fails | [.claude/skills/run-checks/](../.claude/skills/run-checks/SKILL.md), [scripts/run_checks.py](../scripts/run_checks.py) |
| 3 | **Guardrail (hook)** | After every Write/Edit, ruff formats and fixes Python and blocks on anything it can't fix | [.claude/settings.json](../.claude/settings.json), [agent-hooks/](../agent-hooks/README.md) |
| 4 | **Specialized subagent** | `api-reviewer`: read-only review of API contract changes against AGENTS.md, consumers and tests | [.claude/agents/api-reviewer.md](../.claude/agents/api-reviewer.md) |
| 5 | **Scoped MCP server** | `bloom-stats`: one read-only tool, `get_booking_stats` (aggregates, no customer data) | [mcp-server/](../mcp-server/README.md), [.mcp.json](../.mcp.json) |
| 6 | **Custom agent** | On-call responder: Grafana alert → gather logs/traces/metrics → headless, read-only Claude Code investigation → report | [incident-response/](../incident-response/README.md) |
| 7 | **Permissions note** | What each agent and tool can and can't touch | [docs/permissions.md](permissions.md) |

## How they fit together
- **Instructions** (1) tell every agent the rules.
- The **skill** (2) and the **hook** (3) enforce them: the hook on every
  edit, the skill before every hand-off.
- The **subagent** (4) and the **MCP server** (5) show narrow capabilities:
  a reviewer that can only read, and a tool that can only count.
- The **custom agent** (6) runs unattended, so it gets the tightest sandbox.
  (7) writes all of that down.

Built under issues #7 (tests, skill, hook), #9 (observability, alert,
responder) and the Module 5 pack (subagent, MCP server, docs).
