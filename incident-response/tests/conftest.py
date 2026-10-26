import json
import sys
from pathlib import Path

import pytest

SAMPLE = Path(__file__).resolve().parents[1] / "sample-alert.json"


@pytest.fixture
def payload():
    """The sample Grafana webhook payload (a fresh copy per test)."""
    return json.loads(SAMPLE.read_text())


@pytest.fixture
def fake_claude(tmp_path):
    """A stand-in for the `claude` CLI: records stdin/args/env, prints a JSON result."""

    def make(result="## Summary\nAll good.", is_error=False, exit_code=0, stdout=None):
        if stdout is None:
            stdout = json.dumps(
                {
                    "type": "result",
                    "is_error": is_error,
                    "result": result,
                    "num_turns": 3,
                    "total_cost_usd": 0.12,
                }
            )
        script = tmp_path / "fake_claude.py"
        script.write_text(
            "import json, os, sys\n"
            f"open({str(tmp_path / 'stdin.txt')!r}, 'w').write(sys.stdin.read())\n"
            f"called = {{'args': sys.argv[1:], 'env': dict(os.environ), 'cwd': os.getcwd()}}\n"
            f"open({str(tmp_path / 'args.json')!r}, 'w').write(json.dumps(called))\n"
            f"sys.stdout.write({stdout!r})\n"
            f"sys.exit({exit_code})\n"
        )
        return [sys.executable, str(script)]

    return make
