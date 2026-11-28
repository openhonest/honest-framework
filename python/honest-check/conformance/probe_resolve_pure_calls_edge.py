# scenario: resolve_pure_calls
# inherits: hd=python/honest-check/honest-check.hd::resolve_pure_calls -> feature=specs/features/honest-check.feature::resolve_pure_calls returns invalid_role for an edge target -> test=python/honest-check/conformance/probe_resolve_pure_calls_edge.py::probe_resolve_pure_calls_edge
"""Check that the resolver returns invalid_role for an edge-role target."""

_MODULE = {'name': 'consumer',
 'functions': [{'name': 'load',
                'role': 'fn',
                'side_effects': [],
                'pure_calls': ['utils.edgefn']}]}
_DECLARATIONS = {'utils': {'name': 'utils',
           'functions': [{'name': 'edgefn',
                          'role': 'edge',
                          'side_effects': []}]}}
_EXPECTED = [{'caller': 'load',
  'target': 'utils.edgefn',
  'module': 'utils',
  'status': 'invalid_role'}]


def probe_resolve_pure_calls_edge():
    """Compare the complete ordered resolution result."""
    try:
        from honest_check.seams import resolve_pure_calls
    except ImportError as exc:
        return [f"cannot import resolve_pure_calls: {exc}"]

    got = resolve_pure_calls(_MODULE, _DECLARATIONS)
    if got != _EXPECTED:
        return [f"resolve_pure_calls returned {got!r}, expected {_EXPECTED!r}"]
    return []
