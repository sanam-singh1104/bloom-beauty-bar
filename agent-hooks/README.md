# agent-hooks

Automatic code-style guardrails, so formatting and linting never depend on
someone remembering to run them. Both use [ruff](https://docs.astral.sh/ruff/)
with the config in `backend/pyproject.toml`.

| File                | What it is                                          | Runs when |
|---------------------|-----------------------------------------------------|-----------|
| `ruff-on-edit.sh`   | Claude Code hook launcher (finds the venv Python)   | After the agent writes or edits any file |
| `ruff_on_edit.py`   | The hook logic                                      | (called by the launcher) |
| `pre-commit`        | Optional git hook for everyone, human or agent      | `git commit`, once enabled |

## 1. Agent hook: ruff on every edit (on by default)

Registered in [`.claude/settings.json`](../.claude/settings.json) as a
`PostToolUse` hook on `Write|Edit|MultiEdit`, so it's active for anyone who
opens this repo in Claude Code.

After every file write, Claude Code pipes the tool call (JSON) to
`ruff-on-edit.sh`, which runs `ruff_on_edit.py` with `backend/.venv`'s Python:

1. Ignores anything that isn't a `.py` file inside this repo (and skips
   `.venv`, `__pycache__`, etc.).
2. Runs `ruff check --fix` then `ruff format` on **just that file**, so
   import order, unused imports, spacing, quotes, and line wrapping are fixed
   in place.
3. Runs `ruff check` again:
   - **clean** → exits 0, silently.
   - **problems ruff can't auto-fix** (e.g. ambiguous names, bugbear
     warnings, overlong strings) → exits **2** and prints them on stderr.
     Claude Code feeds that back to the agent as a blocking error, so it fixes
     the problem before moving on.
4. Never blocks for setup problems: if ruff or Python is missing it prints a
   note and exits 0.

Example of the feedback the agent gets:

```
ruff found problems it couldn't auto-fix in backend/app/_hook_probe.py
(the file was formatted and auto-fixable issues were fixed):
backend\app\_hook_probe.py:8:1: E741 Ambiguous variable name: `l`
```

**Requirements:** `backend/.venv` with dev requirements
(`pip install -r backend/requirements-dev.txt`), and bash (Git Bash on
Windows, which Claude Code uses for hooks).

**Review or disable:** run `/hooks` in Claude Code, or remove the entry from
`.claude/settings.json`. To turn it off just for yourself, set
`"disableAllHooks": true` in `.claude/settings.local.json` (gitignored).

**Test it by hand** (from the repo root, Git Bash):

```
py -c "import json; print(json.dumps({'tool_input': {'file_path': 'backend/app/main.py'}}))" \
  | bash agent-hooks/ruff-on-edit.sh; echo "exit=$?"
```

## 2. Git pre-commit hook (optional)

Blocks a commit if `backend/` fails `ruff check` or `ruff format --check`.
Catches edits made outside Claude Code. Enable once per clone:

```
git config core.hooksPath agent-hooks
```

Fix failures with `py scripts/run_checks.py --fix`. Undo with
`git config --unset core.hooksPath`.

## Related

The [`run-checks` skill](../.claude/skills/run-checks/SKILL.md) runs the full
gate (lint + format check + all tests) in one command:
`py scripts/run_checks.py`.
