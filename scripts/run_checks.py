"""Run every check the project cares about, in one command.

    py scripts/run_checks.py               # lint + format check + all tests
    py scripts/run_checks.py --fix         # auto-fix lint and format first
    py scripts/run_checks.py --unit        # only unit tests (fast)
    py scripts/run_checks.py --integration # only integration tests
    py scripts/run_checks.py -- -k cancel  # extra args after -- go to pytest

(`python3` instead of `py` on macOS/Linux.) Uses backend/.venv if it exists.
Covers backend/, incident-response/ (the on-call responder) and mcp-server/. Exits non-zero
if any step fails; all steps run regardless so you see everything at once.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
RESPONDER = ROOT / "incident-response"
MCP_SERVER = ROOT / "mcp-server"


def venv_python(project: Path = BACKEND) -> Path | None:
    for candidate in (
        project / ".venv" / "Scripts" / "python.exe",
        project / ".venv" / "bin" / "python",
    ):
        if candidate.exists():
            return candidate
    return None


def reexec_in_venv() -> None:
    """Re-run this script with the backend venv's Python, if we're not in it."""
    python = venv_python()
    if python and Path(sys.prefix).resolve() != python.parents[1].resolve():
        result = subprocess.run([str(python), __file__, *sys.argv[1:]])
        sys.exit(result.returncode)


def run(name: str, cmd: list[str], cwd: Path) -> bool:
    print(f"\n=== {name} ===\n$ {' '.join(cmd)}", flush=True)
    ok = subprocess.run(cmd, cwd=cwd).returncode == 0
    print(f"--- {name}: {'PASS' if ok else 'FAIL'}", flush=True)
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fix", action="store_true", help="apply ruff fixes and formatting")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--unit", action="store_true", help="only unit tests")
    scope.add_argument("--integration", action="store_true", help="only integration tests")
    parser.add_argument("pytest_args", nargs="*", help="extra pytest args (after --)")
    args = parser.parse_args()

    py = sys.executable
    results: dict[str, bool] = {}

    # Each project has its own pyproject.toml (same ruff rules).
    projects = [BACKEND, RESPONDER, MCP_SERVER]
    if args.fix:
        results["ruff fix"] = all(
            run(f"ruff fix {d.name}", [py, "-m", "ruff", "check", "--fix", "."], d)
            for d in projects
        )
        results["ruff format"] = all(
            run(f"ruff format {d.name}", [py, "-m", "ruff", "format", "."], d) for d in projects
        )
    else:
        results["ruff lint"] = all(
            run(f"ruff lint {d.name}", [py, "-m", "ruff", "check", "."], d) for d in projects
        )
        results["ruff format"] = all(
            run(f"ruff format {d.name}", [py, "-m", "ruff", "format", "--check", "."], d)
            for d in projects
        )

    node = shutil.which("node")
    if node:
        ok = all(
            run(f"js syntax {f.name}", [node, "--check", str(f)], ROOT)
            for f in sorted(FRONTEND.glob("*.js"))
        )
        results["js syntax"] = ok
    else:
        print("\n=== js syntax ===\nskipped: node not on PATH", flush=True)

    pytest_cmd = [py, "-m", "pytest"]
    if args.unit:
        pytest_cmd += ["-m", "unit"]
    elif args.integration:
        pytest_cmd += ["-m", "integration"]
    pytest_cmd += args.pytest_args
    results["tests"] = run("tests", pytest_cmd, BACKEND)
    # The responder's tests are all fast and self-contained (no app, no DB).
    if not args.integration:
        results["responder tests"] = run(
            "responder tests", [py, "-m", "pytest", *args.pytest_args], RESPONDER
        )
        # mcp-server/.venv has the MCP SDK for the protocol tests; without it
        # those are skipped and only the stats tests run.
        mcp_py = str(venv_python(MCP_SERVER) or py)
        results["mcp-server tests"] = run(
            "mcp-server tests", [mcp_py, "-m", "pytest", *args.pytest_args], MCP_SERVER
        )

    print("\n=== summary ===")
    for name, ok in results.items():
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
    all_ok = all(results.values())
    print("\nAll checks passed." if all_ok else "\nSome checks FAILED.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    if os.environ.get("RUN_CHECKS_NO_VENV") != "1":
        reexec_in_venv()
    sys.exit(main())
