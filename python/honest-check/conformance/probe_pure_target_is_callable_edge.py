# scenario: pure_target_is_callable
# inherits: hd=python/honest-check/honest-check.hd::pure_target_is_callable -> feature=specs/features/honest-check.feature::pure_target_is_callable returns false for a target whose role is edge -> test=python/honest-check/conformance/probe_pure_target_is_callable_edge.py::probe_pure_target_is_callable_edge
"""The retired edge role names no new surface, so a pure call onto it is not callable."""

# utils declares edgefn with the retired edge role; the grammar reads edge as
# column 1, validation withdraws it, and pure_target_is_callable refuses it.
# A sibling published plain fn (answer) pins the non-trivial true answer so the
# probe cannot pass against a stub that always returns False.
_UTILS = (
    "module utils\n"
    '  edge fn edgefn : () -> int note "retired edge surface"\n'
    '  fn answer : () -> int note "returns one"\n'
)

_CASES = [
    {"given": {"target": "utils.edgefn"}, "expect": False},
    {"given": {"target": "utils.answer"}, "expect": True},
]


def probe_pure_target_is_callable_edge():
    """A target whose declared role is edge is refused; a published plain fn is callable."""
    try:
        from honest_check import pure_target_is_callable
    except ImportError as exc:
        return [f"cannot import pure_target_is_callable: {exc}"]
    from honest_design import read_hd

    utils = read_hd(_UTILS)["ok"]["modules"][0]
    declarations = {utils["name"]: utils}

    bad = []
    for case in _CASES:
        got = pure_target_is_callable(case["given"]["target"], declarations)
        if got != case["expect"]:
            bad.append(
                f"pure_target_is_callable({case['given']['target']!r}, declarations) "
                f"-> {got!r}, expected {case['expect']!r}"
            )
    return bad
