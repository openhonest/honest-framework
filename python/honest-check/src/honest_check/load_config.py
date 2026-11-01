"""The config reader on the filesystem side (honest-check.hd: load_config, role reader).

It finds honest-check.toml in the nearest ancestor directory of the working
directory, reads it, and resolves the project's declared per-rule settings into
the RuleConfig map the orchestrator passes to check_source. It reads the
filesystem and resolves what it read: it does not parse source, check, or write.

honest-check configures only the rules it runs, and it runs exactly one
configurable rule: HC-OR003, whose single setting min_run has no built-in
default. HC-P008 (max_lines) and HC-P012 (max_mocks) are honest-test's rules
and never appear here. So the resolved map is {"HC-OR003": {"min_run": N}} when
the project sets min_run = N under [rules.HC-OR003], and the empty map when no
honest-check.toml exists or it sets nothing — there is no default to fill in, so
a project that sets nothing leaves HC-OR003 unconfigured. Absence is resolved
here, at the boundary, as an explicit branch, never a value invented downstream.
"""

import os
import tomllib

from honest_check.types import RuleConfig

_CONFIG_FILENAME = "honest-check.toml"
_RULE_ID = "HC-OR003"
_SETTING = "min_run"


def _nearest_config(start: str) -> str:
    """Walk from start up to the filesystem root and return the path of the
    nearest honest-check.toml, or the empty string when no ancestor holds one.
    The empty string is the explicit "no config" case, resolved here."""
    current = start
    while True:
        candidate = os.path.join(current, _CONFIG_FILENAME)
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            return ""
        current = parent


def _resolve(parsed: dict) -> RuleConfig:
    """Resolve a parsed honest-check.toml into the RuleConfig map. HC-OR003 is
    the one configurable rule and min_run its one setting; the map carries
    HC-OR003 only when the project declared min_run, and is empty otherwise.
    Each missing layer is a visible branch, because min_run has no default."""
    if "rules" not in parsed:
        return {}
    rules = parsed["rules"]
    if _RULE_ID not in rules:
        return {}
    rule = rules[_RULE_ID]
    if _SETTING not in rule:
        return {}
    return {_RULE_ID: {_SETTING: rule[_SETTING]}}


def load_config() -> RuleConfig:
    """Find honest-check.toml in the nearest ancestor of the working directory,
    read it, and resolve the project's declared per-rule settings. The empty map
    when there is no toml or it sets nothing."""
    path = _nearest_config(os.getcwd())
    if path == "":
        return {}
    with open(path, "rb") as handle:
        parsed = tomllib.load(handle)
    return _resolve(parsed)
