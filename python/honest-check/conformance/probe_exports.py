"""probe_exports pins the exact published export surface of the honest-check
package. The package's __init__.py re-exports its declared functions and sets
__all__ to the exact list of published names, the surface HC-REF005 crosses
against the declaration. No suite case reads __all__, and every name stays
importable whatever __all__ holds, because __all__ governs only
`from honest_check import *`. So a change that empties one __all__ entry to ""
survives every other test. This probe makes that change fail: it compares
honest_check.__all__ against the exact pinned list of names below, and it checks
that each name in __all__ names a real callable export.

The pinned list is copied verbatim from the current source. The source
docstring calls this surface "the twenty-three published declared functions",
but the source actually declares twenty-four names, so the prose count has
drifted from the list. This probe pins what the source declares, twenty-four
names, not the stale count in the prose.

A stub that returns the pinned list as __all__ but drops a real export would
pass the first check and fail the second, so the probe is not vacuous on either
side.
"""

# The exact published export surface, copied verbatim from
# src/honest_check/__init__.py. Emptying any one entry to "" in the source makes
# honest_check.__all__ differ from this list, which this probe reports.
_EXPECTED_ALL = [
    "check_auth",
    "check_paths",
    "check_references",
    "check_roles",
    "check_source",
    "cross_declaration",
    "discover_files",
    "enforced_rules_of",
    "format_github",
    "format_human",
    "format_json",
    "format_junit",
    "load_config",
    "load_project_config",
    "main",
    "pair_source",
    "parse_args",
    "prepare_report",
    "read_declaration",
    "read_format_manifest",
    "read_source",
    "resolve_exit_code",
    "run_check",
    "startup_check",
    "write_report",
]


def probe_exports():
    """honest_check.__all__ equals the exact pinned list of published names, and
    every name in __all__ is importable from honest_check and callable, so the
    list names real exports and nothing more."""
    try:
        import honest_check
    except ImportError as exc:
        return [f"cannot import honest_check: {exc}"]

    bad = []

    published = list(getattr(honest_check, "__all__", []))
    if published != _EXPECTED_ALL:
        bad.append(
            f"__all__ is {published}, expected {_EXPECTED_ALL}"
        )

    for name in published:
        exported = getattr(honest_check, name, None)
        if exported is None:
            bad.append(f"__all__ names {name!r}, which honest_check does not export")
            continue
        if not callable(exported):
            bad.append(f"__all__ names {name!r}, which is not callable: {exported!r}")

    return bad
