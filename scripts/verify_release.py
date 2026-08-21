from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ("core", "plugins", "adapters", "gui", "migrations", "tests", "docs", "examples", "docker")
FORBIDDEN = ("P10",)
PROJECT_NAME = "BuildCostIQ"


def main() -> int:
    missing = [name for name in REQUIRED if not (ROOT / name).exists()]
    if missing:
        print(f"Missing release paths: {', '.join(missing)}", file=sys.stderr)
        return 1
    if PROJECT_NAME not in (ROOT / "README.md").read_text(encoding="utf-8"):
        print("README project name does not match BuildCostIQ", file=sys.stderr)
        return 1
    for path in ROOT.rglob("*.py"):
        if any(part in {".venv", "runtime", ".git"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in FORBIDDEN) and path.name not in {"test_core.py", "verify_release.py"}:
            print(f"Forbidden capability token in {path}", file=sys.stderr)
            return 1
    result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
