"""honest-check.toml configuration (spec §3.1).

Pure normalization + predicates. File discovery and reading happen at the CLI
boundary; this module operates on an already-parsed dict so it stays I/O-free.

    [check]
    paths    = [...]
    exclude  = [...]
    severity = "warning"

    [rules]
    disable  = ["HC-P006"]
"""
from __future__ import annotations

import fnmatch

DEFAULT_CONFIG = {
    "paths": [],
    "exclude": [],
    "severity": "warning",
    "disable": [],
}

_SEVERITY_RANK = {"error": 3, "warning": 2, "info": 1}


def normalize_config(raw: dict) -> dict:
    """Turn a parsed honest-check.toml dict into the flat config honest-check uses."""
    check = raw.get("check", {})
    rules = raw.get("rules", {})
    return {
        "paths": list(check.get("paths", [])),
        "exclude": list(check.get("exclude", [])),
        "severity": check.get("severity", "warning"),
        "disable": list(rules.get("disable", [])),
    }


def meets_severity(severity: str, threshold: str) -> bool:
    """True if `severity` is at least the reporting threshold."""
    return _SEVERITY_RANK.get(severity, 0) >= _SEVERITY_RANK.get(threshold, 2)


def is_excluded(path: str, patterns) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)
