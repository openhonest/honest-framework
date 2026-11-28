# scenario: pure_target_is_callable
# inherits: hd=python/honest-check/honest-check.hd::pure_target_is_callable -> feature=specs/features/honest-check.feature::pure_target_is_callable returns false for an interior unpublished function -> test=python/honest-check/conformance/probe_pure_target_is_callable_interior.py::probe_pure_target_is_callable_interior
"""A pure dependency onto an unexported interior function is refused: the predicate returns false."""

# utils declares `helper` as a plain fn with no side effects, but publishes it
# through no entry and no export — only `answer` is reached by an entry. The
# interior `helper` is the reach into the core the rule refuses.
_UTILS = (
    "module utils\n"
    '  fn answer : () -> int note "the published pure way in"\n'
    '  fn helper : () -> int note "an interior function no entry reaches"\n'
    '  entry "import utils" -> answer\n'
)

# A published-pure control: `answer` IS reached by an entry, so the predicate
# must return true for it. This pins the non-trivial side a constant stub cannot fake.
_CASES = [
    {"target": "utils.helper", "expect": False},  # interior, unpublished -> false
    {"target": "utils.answer", "expect": True},   # published pure fn -> true
]


def probe_pure_target_is_callable_interior():
    """An interior unpublished pure fn is not a callable pure target; a published one is."""
    try:
        from honest_check.seams import pure_target_is_callable
    except ImportError as exc:
        return [f"cannot import pure_target_is_callable: {exc}"]
    from honest_design import read_hd

    utils = read_hd(_UTILS)["ok"]["modules"][0]
    declarations = {utils["name"]: utils}

    bad = []
    for case in _CASES:
        got = pure_target_is_callable(case["target"], declarations)
        if got != case["expect"]:
            bad.append(
                f"pure_target_is_callable({case['target']!r}, declarations) -> "
                f"{got!r}, expected {case['expect']!r}"
            )
    return bad
