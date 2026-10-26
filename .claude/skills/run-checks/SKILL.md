---
name: run-checks
description: Run Bloom Beauty Bar's full quality gate (ruff lint, ruff format check, JS syntax check if node is available, and all unit + integration tests) with one command, then fix anything that fails. Use before committing, before closing an issue, after a refactor, or whenever asked to "run the checks", "run the tests", or "make sure everything passes".
---

# run-checks

One command runs every check for this repo:

```
py scripts/run_checks.py            # Windows
python3 scripts/run_checks.py       # macOS / Linux
```

It re-runs itself inside `backend/.venv` if that exists, runs every step even
if an earlier one fails, prints a PASS/FAIL summary, and exits non-zero if
anything failed.

| Step             | What it runs                                                   |
|------------------|----------------------------------------------------------------|
| ruff lint        | `ruff check .` in `backend/`, `incident-response/`, `mcp-server/` |
| ruff format      | `ruff format --check .` in the same three                      |
| js syntax        | `node --check frontend/*.js` (skipped if no node)              |
| tests            | `pytest` in `backend/` (unit + integration)                    |
| responder tests  | `pytest` in `incident-response/` (skipped with `--integration`) |
| mcp-server tests | `pytest` in `mcp-server/`, with `mcp-server/.venv` if it exists (otherwise the MCP protocol tests are skipped) |

Options:
- `--fix` applies ruff's autofixes and formatting instead of only checking.
- `--unit` / `--integration` limit the test step (`pytest -m unit|integration`).
- Anything after `--` goes to pytest, e.g. `-- -k cancel -x`.

## Procedure

1. **Setup, if `backend/.venv` is missing:** from `backend/`, run
   `py -m venv .venv` then `.venv\Scripts\python -m pip install -r requirements-dev.txt`
   (`.venv/bin/python` on macOS/Linux).
2. **Run** `py scripts/run_checks.py` from the repo root.
3. **If ruff fails:** run `py scripts/run_checks.py --fix`, review the diff
   (`git diff`), and fix by hand anything ruff can't fix (e.g. long lines,
   bugbear warnings). Don't add `# noqa` or widen the ignore list in
   `backend/pyproject.toml` to make a failure go away unless the rule is
   genuinely wrong for this code; say so if you do.
4. **If tests fail:** read the failure, fix the code (or the test, only if the
   test is wrong about the spec in `product-spec.md`), and re-run just that
   test with `py scripts/run_checks.py -- -k <name>` before the full run.
5. **Re-run the full command** until the summary says `All checks passed.`
6. **Report** the summary lines (PASS/FAIL per step and the pytest count) to
   the user. If you stopped with failures, say which and why; never report a
   pass you didn't see.

## Notes

- Tests never touch the real database: each test gets its own temporary
  SQLite file (see `backend/tests/conftest.py`).
- Unit tests live in `backend/tests/unit/` (no app, no DB); integration tests
  in `backend/tests/integration/` (HTTP API and store against SQLite).
- The `agent-hooks/` ruff hook formats Python files on every edit, so lint
  failures here are usually things ruff can't auto-fix.
