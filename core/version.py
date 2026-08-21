"""Single runtime version source.

The editable checkout reads ``pyproject.toml`` first, so changing the project
version takes effect on the next process start without reinstalling the
package.  Installed wheels fall back to package metadata.  An explicit
``BUILDCOSTIQ_VERSION`` environment value is useful for CI and release builds.
"""

from __future__ import annotations

import importlib.metadata
import os
import re
from pathlib import Path


_VERSION_PATTERN = re.compile(r"^\s*version\s*=\s*[\"']([^\"']+)[\"']\s*$", re.MULTILINE)


def normalize_version(value: object) -> str:
    """Return the UI/API form, e.g. ``0.8.0rc1`` → ``0.8.0-rc1``."""
    text = str(value or "").strip().lstrip("vV")
    if not text:
        return "0.0.0-dev"
    return re.sub(r"(?<![-.])(a|b|rc|post)(\d+)$", r"-\1\2", text, flags=re.IGNORECASE)


def _version_from_pyproject() -> str:
    path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    try:
        match = _VERSION_PATTERN.search(path.read_text(encoding="utf-8"))
    except OSError:
        return ""
    return match.group(1) if match else ""


def current_version() -> str:
    """Resolve the current project version without duplicating constants."""
    for candidate in (
        os.environ.get("BUILDCOSTIQ_VERSION", ""),
        _version_from_pyproject(),
    ):
        if str(candidate).strip():
            return normalize_version(candidate)
    try:
        return normalize_version(importlib.metadata.version("buildcostiq"))
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0-dev"


APP_VERSION = current_version()

__all__ = ["APP_VERSION", "current_version", "normalize_version"]
