# scenario: pure_target_is_callable
# inherits: hd=python/honest-check/honest-check.hd::pure_target_is_callable -> feature=specs/features/honest-check.feature::pure_target_is_callable returns false for a target the module does not declare -> test=python/honest-check/conformance/probe_pure_target_is_callable_missing.py::probe_pure_target_is_callable_missing
"""A target whose module is in view but declares no function of that name is not callable (false)."""

# The scenario's own case: target "utils.absent", declarations include utils,
# which declares answer (published) but NO function named absent. A missing
# function is not callable, so the predicate returns false.
_DECLARATIONS = {
    "utils": {
        "name": "utils",
        "functions": [
            {"name": "answer", "role": "fn", "side_effects": []},
        ],
        "entries": [{"callsite": "import utils", "target": "answer"}],
    }
}

_CASES = [
    # The scenario under test: the target module is in view but declares no
    # function named "absent" -> false.
    {"given": {"target": "utils.absent", "declarations": _DECLARATIONS}, "expect": False},
    # Positive control, so a `return False` stub cannot pass this probe. Drawn
    # from the sibling scenario "pure_target_is_callable returns true for a
    # published pure fn": "utils.answer" is a plain fn, no side effects,
    # published through a valid entry -> true. (See GAPS: this True is fixed by
    # that sibling scenario, not by the missing-target scenario.)
    {"given": {"target": "utils.answer", "declarations": _DECLARATIONS}, "expect": True},
]


def probe_pure_target_is_callable_missing():
    """A target the module does not declare is not callable; a published pure fn is."""
    try:
        from honest_check.seams import pure_target_is_callable
    except ImportError as exc:
        return [f"cannot import pure_target_is_callable: {exc}"]

    bad = []
    for case in _CASES:
        got = pure_target_is_callable(**case["given"])
        if got != case["expect"]:
            bad.append(
                f"pure_target_is_callable({case['given']['target']!r}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
