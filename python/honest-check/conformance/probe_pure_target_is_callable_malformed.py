# scenario: pure_target_is_callable
# inherits: hd=python/honest-check/honest-check.hd::pure_target_is_callable -> feature=specs/features/honest-check.feature::pure_target_is_callable returns false for a malformed target with no module half -> test=python/honest-check/conformance/probe_pure_target_is_callable_malformed.py::probe_pure_target_is_callable_malformed
"""A pure_call target string with no dot has no module half and is not callable: the predicate returns false."""

# The target "answer" has no dot, so it carries no module half. The scenario
# says declarations merely "holds the loaded declarations"; a concrete non-empty
# map is given so the row states its whole input, and the predicate must still
# return false because the malformed target has no module name to key on.
_DECLARATIONS = {
    "utils": {
        "name": "utils",
        "functions": [{"name": "answer", "role": "fn", "side_effects": []}],
        "entries": [{"callsite": "answer", "target": "answer"}],
        "exports": ["answer"],
    }
}

_CASES = [
    {"given": {"target": "answer", "declarations": _DECLARATIONS}, "expect": False},
]


def probe_pure_target_is_callable_malformed():
    """A malformed target with no module half returns false."""
    try:
        from honest_check.seams import pure_target_is_callable
    except ImportError as exc:
        return [f"cannot import pure_target_is_callable: {exc}"]

    bad = []
    for case in _CASES:
        got = pure_target_is_callable(**case["given"])
        if got != case["expect"]:
            bad.append(
                f"pure_target_is_callable({case['given']['target']!r}, ...) "
                f"-> {got!r}, expected {case['expect']!r}"
            )
    return bad
