# scenario: resolve_pure_calls returns invalid_role for impure targets
# inherits: hd=python/honest-check/honest-check.hd::resolve_pure_calls -> feature=specs/features/honest-check.feature::resolve_pure_calls returns invalid_role for impure targets
"""Check that the resolver returns invalid_role for impure targets."""

_MODULE = {'name': 'consumer',
 'functions': [{'name': 'load',
                'role': 'fn',
                'side_effects': [],
                'pure_calls': ['world.read', 'effects.read', 'world.answer']},
               {'name': 'answer', 'role': 'fn', 'side_effects': []}]}
_DECLARATIONS = {'world': {'name': 'world',
           'functions': [{'name': 'read',
                          'role': 'boundary_in',
                          'side_effects': []},
                         {'name': 'answer', 'role': 'fn', 'side_effects': []}]},
 'effects': {'name': 'effects',
             'functions': [{'name': 'read',
                            'role': 'fn',
                            'side_effects': [{'direction': 'reads',
                                              'target': 'file:data',
                                              'module': '',
                                              'door': ''}]}]}}
_EXPECTED = [{'caller': 'load',
  'target': 'world.read',
  'module': 'world',
  'status': 'invalid_role'},
 {'caller': 'load',
  'target': 'effects.read',
  'module': 'effects',
  'status': 'invalid_role'},
 {'caller': 'load',
  'target': 'world.answer',
  'module': 'world',
  'status': 'invalid_role'}]


def probe_resolve_pure_calls_impure():
    """Compare the complete ordered resolution result."""
    try:
        from honest_check.seams import resolve_pure_calls
    except ImportError as exc:
        return [f"cannot import resolve_pure_calls: {exc}"]

    got = resolve_pure_calls(_MODULE, _DECLARATIONS)
    if got != _EXPECTED:
        return [f"resolve_pure_calls returned {got!r}, expected {_EXPECTED!r}"]
    return []
