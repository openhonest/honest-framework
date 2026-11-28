# scenario: pure_target_is_callable
# inherits: hd=python/honest-check/honest-check.hd::pure_target_is_callable -> feature=specs/features/honest-check.feature::pure_target_is_callable reads the module's publication surface and boundary -> test=python/honest-check/conformance/probe_pure_target_is_callable_surface.py::probe_pure_target_is_callable_surface
"""pure_target_is_callable reads a module's publication surface (`exports`, `__all__`) and
counts a `boundary_out` as a boundary when deciding whether a pure target is published."""

# Case A — exports as a surface. The module HAS a boundary (boundary_in `door`),
# so the boundaryless-publishes-all shortcut does NOT apply. The target `answer`
# is published ONLY through the module's `exports` key. It must be callable.
_EXPORTS_ONLY = {
    'utils': {
        'name': 'utils',
        'functions': [
            {'name': 'answer', 'role': 'fn', 'side_effects': []},
            {'name': 'door', 'role': 'boundary_in', 'side_effects': []},
        ],
        'exports': ['answer'],
    },
}

# Case B — __all__ as a surface. Same boundaried shape, but the target `answer`
# is published ONLY through the module's `__all__` key (no exports, no entry).
# It must still be callable.
_ALL_ONLY = {
    'utils': {
        'name': 'utils',
        'functions': [
            {'name': 'answer', 'role': 'fn', 'side_effects': []},
            {'name': 'door', 'role': 'boundary_in', 'side_effects': []},
        ],
        '__all__': ['answer'],
    },
}

# Case C — a boundary_out is a boundary. The module's ONLY boundary is a
# `boundary_out` (`sink`); the target `answer` is named by no entry, no export,
# no __all__ — it is interior. Because boundary_out counts as a boundary, the
# boundaryless-publishes-all shortcut must NOT apply, so `answer` is unpublished
# and NOT callable.
_BOUNDARY_OUT_INTERIOR = {
    'utils': {
        'name': 'utils',
        'functions': [
            {'name': 'answer', 'role': 'fn', 'side_effects': []},
            {'name': 'sink', 'role': 'boundary_out', 'side_effects': []},
        ],
    },
}

_CASES = [
    {'given': {'target': 'utils.answer', 'declarations': _EXPORTS_ONLY}, 'expect': True},
    {'given': {'target': 'utils.answer', 'declarations': _ALL_ONLY}, 'expect': True},
    {'given': {'target': 'utils.answer', 'declarations': _BOUNDARY_OUT_INTERIOR}, 'expect': False},
]


def probe_pure_target_is_callable_surface():
    """The publication surface is `exports` ∪ `__all__` ∪ entry targets, and a
    boundary_out makes a module non-boundaryless."""
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
