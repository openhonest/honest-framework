# scenario: distribution_pure_dependencies includes only resolved calls from the caller distribution
# inherits: hd=python/honest-check/honest-check.hd::distribution_pure_dependencies -> feature=specs/features/honest-check.feature::distribution_pure_dependencies includes only resolved calls from the caller distribution
"""Collect only successful dependency evidence owned by the caller distribution."""

_PATHS = {
    "owner": "packages/owner/owner.hd",
    "sibling": "packages/owner/sibling.hd",
    "other": "packages/other/other.hd",
}
_CALLS = {
    "owner": [
        {"caller": "start", "target": "utils.answer", "module": "utils", "status": "resolved"},
    ],
    "sibling": [
        {"caller": "build", "target": "math.add", "module": "math", "status": "resolved"},
        {"caller": "build", "target": "missing.answer", "module": "missing", "status": "unresolved"},
        {"caller": "build", "target": "world.read", "module": "world", "status": "invalid_role"},
    ],
    "other": [
        {"caller": "load", "target": "external.answer", "module": "external", "status": "resolved"},
    ],
}
_EXPECTED = {"utils", "math"}


def probe_distribution_pure_dependencies_resolved():
    """Return neither failed calls nor successful calls from another directory."""
    try:
        from honest_check.seams import distribution_pure_dependencies
    except ImportError as exc:
        return [f"cannot import distribution_pure_dependencies: {exc}"]

    root_paths = {"owner": "owner.hd", "sibling": "sibling.hd", "other": "other/other.hd", "unplaced": ""}
    root_calls = {
        **_CALLS,
        "sibling": [
            *_CALLS["sibling"],
            {"caller": "build", "target": "utils.answer", "module": "utils", "status": "resolved"},
        ],
        "unplaced": [{"caller": "probe", "target": "stray.answer", "module": "stray", "status": "resolved"}],
    }
    cases = (("nested distribution", _PATHS, _CALLS), ("root distribution", root_paths, root_calls))
    failures = []
    for description, paths, calls in cases:
        got = distribution_pure_dependencies("owner", paths, calls)
        if got != _EXPECTED:
            failures.append(f"{description}: distribution_pure_dependencies returned {got!r}, expected {_EXPECTED!r}")
    return failures
