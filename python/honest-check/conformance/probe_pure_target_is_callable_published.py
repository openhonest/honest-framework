# scenario: pure_target_is_callable
# inherits: hd=python/honest-check/honest-check.hd::pure_target_is_callable -> feature=specs/features/honest-check.feature::pure_target_is_callable returns true for a published pure fn -> test=python/honest-check/conformance/probe_pure_target_is_callable_published.py::probe_pure_target_is_callable_published
"""pure_target_is_callable returns true for a function another module publishes as a pure way in."""

# utils declares answer as a plain fn with no side effects and publishes it
# through a valid entry (target "answer"), the published-pure-function evidence.
_DECLARATIONS = {
    'utils': {
        'name': 'utils',
        'functions': [{'name': 'answer', 'role': 'fn', 'side_effects': []}],
        'entries': [{'callsite': 'import utils', 'target': 'answer'}],
    },
}

_CASES = [
    {'given': {'target': 'utils.answer', 'declarations': _DECLARATIONS}, 'expect': True},
]


def probe_pure_target_is_callable_published():
    """Returns true for a published pure fn: utils.answer is a plain fn, no side effects, published."""
    try:
        from honest_check.seams import pure_target_is_callable
    except ImportError as exc:
        return [f"cannot import pure_target_is_callable: {exc}"]

    bad = []
    for case in _CASES:
        got = pure_target_is_callable(**case['given'])
        if got != case['expect']:
            bad.append(
                f"pure_target_is_callable({case['given']['target']!r}, ...) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
