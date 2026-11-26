# scenario: resolve_pure_calls returns unresolved for missing targets
# inherits: hd=python/honest-check/honest-check.hd::resolve_pure_calls -> feature=specs/features/honest-check.feature::resolve_pure_calls returns unresolved for missing targets
"""Check that the resolver returns unresolved for missing targets."""

_MODULE = {'name': 'consumer',
 'functions': [{'name': 'load',
                'role': 'fn',
                'side_effects': [],
                'pure_calls': ['absent.answer',
                               'utils.unknown',
                               'consumer.answer']},
               {'name': 'answer', 'role': 'fn', 'side_effects': []}]}
_DECLARATIONS = {'utils': {'name': 'utils',
           'functions': [{'name': 'answer', 'role': 'fn', 'side_effects': []},
                         {'name': 'other', 'role': 'fn', 'side_effects': []}]},
 'consumer': {'name': 'consumer',
              'functions': [{'name': 'answer',
                             'role': 'fn',
                             'side_effects': []}]}}
_EXPECTED = [{'caller': 'load',
  'target': 'absent.answer',
  'module': 'absent',
  'status': 'unresolved'},
 {'caller': 'load',
  'target': 'utils.unknown',
  'module': 'utils',
  'status': 'unresolved'},
 {'caller': 'load',
  'target': 'consumer.answer',
  'module': 'consumer',
  'status': 'unresolved'}]


def probe_resolve_pure_calls_missing():
    """Compare the complete ordered resolution result."""
    try:
        from honest_check.seams import resolve_pure_calls
    except ImportError as exc:
        return [f"cannot import resolve_pure_calls: {exc}"]

    got = resolve_pure_calls(_MODULE, _DECLARATIONS)
    if got != _EXPECTED:
        return [f"resolve_pure_calls returned {got!r}, expected {_EXPECTED!r}"]
    return []
