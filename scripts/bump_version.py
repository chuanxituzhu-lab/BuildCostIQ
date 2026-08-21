"""Update the project version in one place and refresh user-facing metadata."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

from core.version import normalize_version


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"


def _pep440(version: str) -> str:
    return normalize_version(version).replace("-rc", "rc").replace("-alpha", "a").replace("-beta", "b")


def _current_raw() -> str:
    match = re.search(r"^version\s*=\s*[\"']([^\"']+)[\"']\s*$", PYPROJECT.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise ValueError("pyproject.toml 中没有 project.version")
    return match.group(1)


def _bump_patch(version: str) -> str:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise ValueError(f"无法自动递增版本：{version}")
    return f"{match.group(1)}.{match.group(2)}.{int(match.group(3)) + 1}"


def update_version(version: str) -> str:
    display = normalize_version(version)
    raw = _pep440(display)
    content = PYPROJECT.read_text(encoding="utf-8")
    updated, count = re.subn(r'(^version\s*=\s*[\"\'])[^\"\']+([\"\']\s*$)', rf"\g<1>{raw}\g<2>", content, count=1, flags=re.MULTILINE)
    if count != 1:
        raise ValueError("无法更新 pyproject.toml 的 project.version")
    PYPROJECT.write_text(updated, encoding="utf-8")

    replacements = {
        ROOT / "README.md": (r"BuildCostIQ version `v[^`]+`", f"BuildCostIQ version `v{display}`"),
        ROOT / "RELEASE_MANIFEST.md": (r"^# BuildCostIQ Release Manifest — v[^\r\n]+", f"# BuildCostIQ Release Manifest — v{display}"),
    }
    for path, (pattern, replacement) in replacements.items():
        if path.exists():
            text = path.read_text(encoding="utf-8")
            path.write_text(re.sub(pattern, replacement, text, count=1, flags=re.MULTILINE), encoding="utf-8")

    changelog = ROOT / "CHANGELOG.md"
    text = changelog.read_text(encoding="utf-8")
    heading = f"## v{display} - {date.today().isoformat()}"
    if heading not in text:
        text = text.replace("# Changelog\n", f"# Changelog\n\n{heading}\n\n- Version metadata refreshed by scripts/bump_version.py.\n", 1)
        changelog.write_text(text, encoding="utf-8")
    return display


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bump BuildCostIQ version metadata")
    parser.add_argument("version", nargs="?", help="目标版本，例如 0.8.0-rc2")
    parser.add_argument("--patch", action="store_true", help="递增补丁版本")
    args = parser.parse_args(argv)
    if bool(args.version) == bool(args.patch):
        parser.error("请提供目标版本，或使用 --patch（二选一）")
    target = _bump_patch(_current_raw()) if args.patch else args.version
    print(f"BuildCostIQ version → v{update_version(target)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
