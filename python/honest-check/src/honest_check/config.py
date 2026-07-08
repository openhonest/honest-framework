"""honest-check.toml configuration (section 3.1).

Pure: a raw parsed dict in, a normalized config out, plus pure predicates. The file
read and the ancestor search are I/O and live at the cli boundary; this module never
touches the filesystem, so it stays exhaustively testable.

    [check]
    paths     = ["src/"]
    exclude   = ["**/migrations/**", "**/__pycache__/**"]
    severity  = "warning"
    templates = "templates/"

    [rules]
    disable  = ["HC-P006"]
"""

from fnmatch import fnmatch

_DEFAULT_SEVERITY = "warning"


def normalize_config(raw: dict) -> dict:
    """Extract the supported keys from a parsed honest-check.toml, with defaults (section 3.1). Beyond
    [check] and the [rules].disable list, this keeps each per-rule sub-table (e.g. [rules.HC-OR003]
    min_run) in `rule_config` and the [startup] on_error in `startup_on_error`, so no declared key is
    silently dropped."""
    check = raw.get("check", {})
    rules = raw.get("rules", {})
    return {
        "paths": list(check.get("paths", [])),
        "exclude": list(check.get("exclude", [])),
        "severity": check.get("severity", _DEFAULT_SEVERITY),
        "templates": check.get("templates", ""),
        "disable": list(rules.get("disable", [])),
        "rule_config": {name: dict(value) for name, value in rules.items() if name != "disable" and hasattr(value, "items")},
        "startup_on_error": raw.get("startup", {}).get("on_error"),
    }


def empty_config() -> dict:
    """The config when no honest-check.toml is found."""
    return normalize_config({})


def is_excluded(path: str, patterns: list[str]) -> bool:
    """True if `path` matches any exclude glob (section 3.2)."""
    return any(fnmatch(path, pattern) for pattern in patterns)


def resolve_severity(cli_severity, config_severity: str) -> str:
    """--severity (if given) wins over honest-check.toml, which wins over the default."""
    return cli_severity or config_severity or _DEFAULT_SEVERITY


def resolve_paths(cli_paths: list[str], config_paths: list[str]) -> list[str]:
    """CLI paths win; else config paths; else current directory."""
    return cli_paths or config_paths or ["."]
