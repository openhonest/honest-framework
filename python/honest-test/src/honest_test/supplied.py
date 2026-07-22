"""Programmer-supplied test values (section 3.6).

For predicates the analyzer cannot introspect (external lookups), the developer supplies
valid/invalid examples in honest-test.toml. honest-test confirms the valid ones are accepted
and the invalid ones rejected; a predicate classified external with no supplied entry is a
warning (raised by the caller).

supplied_for is pure (a parsed config in, values out). load_config is the thin boundary that
reads and parses the TOML file via the stdlib tomllib - no third-party YAML parser, and none
of YAML's type-inference footguns.
"""

import tomllib
from pathlib import Path

_DEFAULT_STRATEGY = "supplied_only"


def supplied_for(config, predicate_name):
    """The supplied values for a predicate from a parsed honest-test.toml (section 3.6):
    {"valid": [...], "invalid": [...], "strategy": ...}, or None when there is no entry."""
    entry = config.get("predicates", {}).get(predicate_name)
    if entry is None:
        return None
    return {
        "valid": list(entry.get("valid", [])),
        "invalid": list(entry.get("invalid", [])),
        "strategy": entry.get("strategy", _DEFAULT_STRATEGY),
    }


def load_config(path):
    """Read and parse honest-test.toml (the boundary I/O). Returns {} when the file is absent.
    Uses the stdlib tomllib - no dependency, no YAML type inference."""
    file_path = Path(path)
    if not file_path.is_file():
        return {}
    with file_path.open("rb") as handle:
        return tomllib.load(handle)
# honest: enable HC-P004
