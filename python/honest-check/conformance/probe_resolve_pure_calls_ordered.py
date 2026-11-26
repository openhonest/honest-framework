# scenario: resolve_pure_calls preserves resolved occurrences in declaration order
# inherits: hd=python/honest-check/honest-check.hd::resolve_pure_calls -> feature=specs/features/honest-check.feature::resolve_pure_calls preserves resolved occurrences in declaration order
"""Check that the resolver preserves resolved occurrences in declaration order."""

_MODULE = {'name': 'consumer',
 'functions': [{'name': 'load',
                'role': 'reader',
                'side_effects': [],
                'pure_calls': ['utils.answer', 'utils.other', 'utils.answer']},
               {'name': 'answer', 'role': 'fn', 'side_effects': []}]}
_DECLARATIONS = {'utils': {'name': 'utils',
           'functions': [{'name': 'answer', 'role': 'fn', 'side_effects': []},
                         {'name': 'other', 'role': 'fn', 'side_effects': []}]}}
_EXPECTED = [{'caller': 'load',
  'target': 'utils.answer',
  'module': 'utils',
  'status': 'resolved'},
 {'caller': 'load',
  'target': 'utils.other',
  'module': 'utils',
  'status': 'resolved'},
 {'caller': 'load',
  'target': 'utils.answer',
  'module': 'utils',
  'status': 'resolved'}]


def probe_resolve_pure_calls_ordered():
    """Compare the complete ordered resolution result."""
    try:
        from honest_check.seams import resolve_pure_calls
    except ImportError as exc:
        return [f"cannot import resolve_pure_calls: {exc}"]

    got = resolve_pure_calls(_MODULE, _DECLARATIONS)
    if got != _EXPECTED:
        return [f"resolve_pure_calls returned {got!r}, expected {_EXPECTED!r}"]
    return []
