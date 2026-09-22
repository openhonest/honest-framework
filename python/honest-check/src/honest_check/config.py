"""honest-check.toml configuration (section 3.1).

Pure: a raw parsed dict in, a normalized config out, plus pure predicates. The file
read and the ancestor search are I/O and live at the cli boundary; this module never
touches the filesystem, so it stays exhaustively testable.

    [check]
    paths     = ["src/"]
    exclude   = ["**/migrations/**", "**/__pycache__/**"]
    severity  = "warning"
    adoption  = "Boundary"   # section 9.4; absent means the strictest level
    templates = "templates/"
    declaration = "app.hd"   # the module's .hd; HC-R002 and HC-R003 run only where one is named

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
        "adoption": check.get("adoption"),
        "templates": check.get("templates", ""),
        "format_manifest": check.get("format_manifest", ""),
        "component_manifest": check.get("component_manifest", ""),
        "declaration": check.get("declaration", ""),
        "disable": list(rules.get("disable", [])),
        "rule_config": {name: dict(value) for name, value in rules.items() if name != "disable" and hasattr(value, "items")},
        "startup_on_error": raw.get("startup", {}).get("on_error"),
    }


# The documented per-rule settings, written down once. A rule's value is resolved here at the
# boundary and handed to the rule as an argument it cannot omit, rather than defaulted inside the
# rule: a defaulted parameter cannot tell a caller that chose the documented value from one that
# never knew the setting existed, and those are a decision and a wiring bug respectively.
DOCUMENTED_RULE_CONFIG = {
    "HC-OR003": {"min_run": 3},
}


def resolve_rule_config(declared: dict) -> dict:
    """The settings each configurable rule will run with: what the project declared, over the
    documented values. Pure. A project that declares nothing gets the documented values explicitly,
    which is a different fact from a rule quietly falling back to a constant inside itself."""
    resolved = {}
    for rule, documented in DOCUMENTED_RULE_CONFIG.items():
        settings = dict(documented)
        settings.update({k: v for k, v in declared.get(rule, {}).items() if k in documented})
        resolved[rule] = settings
    return resolved


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
