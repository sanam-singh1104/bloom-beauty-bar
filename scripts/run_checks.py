"""Run every check the project cares about, in one command.

    py scripts/run_checks.py               # lint + format check + all tests
    py scripts/run_checks.py --fix         # auto-fix lint and format first
    py scripts/run_checks.py --unit        # only unit tests (fast)
    py scripts/run_checks.py --integration # only integration tests
    py scripts/run_checks.py -- -k cancel  # extra args after -- go to pytest

(`python3` instead of `py` on macOS/Linux.) Uses backend/.venv if it exists.
Exits non-zero if any step fails; all steps run regardless so you see
everything at once.
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


def venv_python() -> Path | None:
    for candidate in (
        BACKEND / ".venv" / "Scripts" / "python.exe",
        BACKEND / ".venv" / "bin" / "python",
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

    if args.fix:
        results["ruff fix"] = run("ruff fix", [py, "-m", "ruff", "check", "--fix", "."], BACKEND)
        results["ruff format"] = run("ruff format", [py, "-m", "ruff", "format", "."], BACKEND)
    else:
        results["ruff lint"] = run("ruff lint", [py, "-m", "ruff", "check", "."], BACKEND)
        results["ruff format"] = run(
            "ruff format", [py, "-m", "ruff", "format", "--check", "."], BACKEND
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
