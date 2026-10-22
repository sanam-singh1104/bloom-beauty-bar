#!/usr/bin/env bash
# Launcher for ruff_on_edit.py: picks the backend venv's Python (which has
# ruff) and passes the hook payload through on stdin. Wired up in
# .claude/settings.json as a PostToolUse hook on Write|Edit.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(dirname "$here")"

for py in "$root/backend/.venv/Scripts/python.exe" "$root/backend/.venv/bin/python"; do
  if [ -x "$py" ]; then
    exec "$py" "$here/ruff_on_edit.py"
  fi
done

for py in python3 python py; do
  if command -v "$py" >/dev/null 2>&1; then
    exec "$py" "$here/ruff_on_edit.py"
  fi
done

echo "ruff hook: no Python found; skipping" >&2
exit 0
