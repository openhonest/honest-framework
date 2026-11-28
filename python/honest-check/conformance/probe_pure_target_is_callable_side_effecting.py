# scenario: pure_target_is_callable
# inherits: hd=python/honest-check/honest-check.hd::pure_target_is_callable -> feature=specs/features/honest-check.feature::pure_target_is_callable returns false for a side-effecting target -> test=python/honest-check/conformance/probe_pure_target_is_callable_side_effecting.py::probe_pure_target_is_callable_side_effecting
"""A side-effecting target is a side-effect seam, not a pure dependency, so the
predicate answers false; a plain published pure fn answers true."""

# The utils module declares a plain pure fn (answer) with no side effects and a
# side-effecting fn (read_file) carrying one declared reads side effect. Both are
# parsed from real .hd source through honest_design.read_hd, never hand-built.
_UTILS_SOURCE = (
    "module utils\n"
    '  fn answer : () -> int note "returns one"\n'
    '  fn read_file : () -> bytes side_effect reads "file:data" note "reads a file"\n'
)

_CASES = [
    # The scenario's case: a side-effecting target is not a pure dependency.
    {"given": "utils.read_file", "expect": False},
    # The published-pure-fn anchor: a non-trivial true a return-False stub fails.
    {"given": "utils.answer", "expect": True},
]


def probe_pure_target_is_callable_side_effecting():
    """pure_target_is_callable returns false for a side-effecting target."""
    try:
        from honest_check.seams import pure_target_is_callable
    except ImportError as exc:
        return [f"cannot import pure_target_is_callable: {exc}"]

    from honest_design import read_hd

    utils = read_hd(_UTILS_SOURCE)["ok"]["modules"][0]
    declarations = {utils["name"]: utils}

    bad = []
    for case in _CASES:
        got = pure_target_is_callable(case["given"], declarations)
        if got != case["expect"]:
            bad.append(
                f"pure_target_is_callable({case['given']!r}, declarations) "
                f"-> {got!r}, expected {case['expect']!r}"
            )
    return bad
