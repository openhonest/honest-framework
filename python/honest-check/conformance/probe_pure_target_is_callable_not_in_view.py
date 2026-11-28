# scenario: pure_target_is_callable
# inherits: hd=python/honest-check/honest-check.hd::pure_target_is_callable -> feature=specs/features/honest-check.feature::pure_target_is_callable returns false for a target the module does not declare -> test=python/honest-check/conformance/probe_pure_target_is_callable_not_in_view.py::probe_pure_target_is_callable_not_in_view
"""A target whose module half is present (has a dot) but whose module is not a
key in the declarations map is not callable (false).

This is the module-not-in-view case the sibling probes do not cover: the sibling
`missing` probe has the module in view but no function of that name; this probe
has the module half present and parseable off the dot, but the module itself is
absent from a non-empty declarations map. The base Then fixes false here: the
predicate is true only when the target module name is a key in declarations, so a
module that is not a key is not callable.
"""

# A non-empty map of OTHER modules. The point under test is the MISSING module
# "ghost", not an empty map: "utils" is in view and declares answer, but there is
# no module named "ghost" at all.
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
    # The case under test: target "ghost.somefn" has a dot, so the module half is
    # "ghost"; "ghost" is not a key in _DECLARATIONS -> false.
    {"given": {"target": "ghost.somefn", "declarations": _DECLARATIONS}, "expect": False},
    # Positive control, so a `return False` stub cannot pass this probe: the
    # published pure fn "utils.answer" is callable -> true. (See GAPS: this True is
    # fixed by the sibling published scenario, not by this not-in-view case.)
    {"given": {"target": "utils.answer", "declarations": _DECLARATIONS}, "expect": True},
]


def probe_pure_target_is_callable_not_in_view():
    """A target whose module is not a key in declarations is not callable; a published pure fn is."""
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
