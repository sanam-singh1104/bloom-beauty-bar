"""Claude Code PostToolUse hook: format and lint a Python file right after it's edited.

Reads the hook payload (JSON) on stdin. For a .py file in this repo it runs
`ruff check --fix` and `ruff format` on that file, then `ruff check` again:

- clean            -> exit 0, silent
- problems remain  -> exit 2 with them on stderr, which Claude Code shows to
                      the agent so it fixes them before moving on
- not a .py file, outside the repo, or ruff missing -> exit 0 (never blocks)
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".venv", "venv", "__pycache__", ".git", "node_modules"}


def edited_file(payload: dict) -> Path | None:
    tool_input = payload.get("tool_input") or {}
    tool_response = payload.get("tool_response") or {}
    raw = tool_input.get("file_path") or tool_response.get("filePath")
    return Path(raw).resolve() if raw else None


def ruff(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "ruff", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    path = edited_file(payload)
    if path is None or path.suffix != ".py" or not path.is_file():
        return 0
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return 0  # outside this repo
    if SKIP_PARTS.intersection(relative.parts):
        return 0

    if ruff("--version").returncode != 0:
        print(
            "ruff hook: ruff isn't installed in this Python; skipping. Install the dev "
            "requirements: backend/.venv python -m pip install -r backend/requirements-dev.txt",
            file=sys.stderr,
        )
        return 0

    target = str(path)
    ruff("check", "--fix", "--quiet", target)
    ruff("format", "--quiet", target)
    remaining = ruff("check", "--output-format", "concise", target)
    if remaining.returncode != 0:
        print(
            f"ruff found problems it couldn't auto-fix in {relative.as_posix()} "
            "(the file was formatted and auto-fixable issues were fixed):\n"
            + remaining.stdout.strip(),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
