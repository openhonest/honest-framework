"""Load [tool.honest_test] from pyproject.toml. I/O at the boundary.

`load_honest_test_config` reads the file; `merge_config` is the pure
defaults-merge step and is the part that gets unit-tested directly.
"""
from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from honest_test.pytest_plugin._types import HonestTestConfig


DEFAULTS: HonestTestConfig = {
    "report_contracts": True,
    "report_pytest_items": True,
    "lint": False,
    "lint_exempt": [],
    "source_roots": [],
    "exclude_patterns": [],
    "private_functions": "skip",
    "coverage_min": 0,
    "coverage_fail_under": False,
    "silent_default_params": [],
    "silent_default_values": ["", "None"],
    "silent_default_exempt": [],
    "silent_default_fail_on_violation": True,
    "browser_step_roots": [],
    "browser_auth_fixture": "page",
    "browser_required_fixture": "harness",
    "browser_forbidden_imports": ["Page", "auth_page"],
}


def merge_config(raw: dict[str, Any]) -> HonestTestConfig:
    """Pure: overlay raw `[tool.honest_test]` table on DEFAULTS."""
    merged = dict(DEFAULTS)
    for key in DEFAULTS:
        if key in raw:
            merged[key] = raw[key]
    return merged  # type: ignore[return-value]


def load_honest_test_config(rootpath: Path) -> HonestTestConfig:
    """Boundary: read pyproject.toml and call merge_config."""
    pyproject = rootpath / "pyproject.toml"
    if not pyproject.is_file():
        return merge_config({})
    with pyproject.open("rb") as fh:
        data = tomllib.load(fh)
    raw = data.get("tool", {}).get("honest_test", {})
    return merge_config(raw)
