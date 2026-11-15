"""Honest probe for honest-check's resolve_project_config (feature Scenario: resolve_project_config).

resolve_project_config is the pure resolver that builds the [check] ProjectConfig
from the raw parsed honest-check.toml table, applying the documented defaults
load_project_config does not: an exclude list, an adoption level resolved to the
strictest 'Declared' when the key is absent or names no level the vocabulary
carries, and a format_manifest path that is the empty string when unset. One case
pins a populated table; one pins the empty table's defaults. A constant stub that
always returned the defaults passes the empty case but fails the populated one.
"""

# Each case: a raw [check] table, and the ProjectConfig record resolve_project_config must build.
_CASES = [
    # Populated: each key read through to the resolved record.
    {
        "data": {"exclude": ["build/*"], "adoption": "Typed", "format_manifest": "manifest.json"},
        "expect": {"exclude": ["build/*"], "adoption": "Typed", "format_manifest": "manifest.json"},
    },
    # Empty table: exclude empty, adoption the strictest 'Declared', format_manifest empty.
    {
        "data": {},
        "expect": {"exclude": [], "adoption": "Declared", "format_manifest": ""},
    },
    # adoption names no level the AdoptionLevel vocabulary carries: resolved to 'Declared'.
    {
        "data": {"adoption": "Nonsense"},
        "expect": {"exclude": [], "adoption": "Declared", "format_manifest": ""},
    },
]


def probe_resolve_project_config():
    """resolve_project_config builds the [check] ProjectConfig, applying the documented defaults."""
    try:
        from honest_check import resolve_project_config
    except ImportError as exc:
        return [f"cannot import resolve_project_config: {exc}"]

    bad = []
    for case in _CASES:
        got = resolve_project_config(data=case["data"])
        if got != case["expect"]:
            bad.append(
                f"resolve_project_config({case['data']!r}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
