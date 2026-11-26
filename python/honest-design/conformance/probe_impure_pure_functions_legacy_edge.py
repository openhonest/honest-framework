# scenario: _impure_pure_functions faults a legacy edge that declares a side effect
# inherits: hd=python/honest-design/honest-design.hd::_impure_pure_functions -> feature=python/honest-design/features/honest-design.feature::_impure_pure_functions faults a legacy edge that declares a side effect

_SOURCE = (
    'module example\n'
    '  edge fn find : (key: str) -> str side_effect reads "file:catalog" note "finds a value"\n'
)
_EXPECTED = ['impure_pure_function']


def probe_impure_pure_functions_legacy_edge():
    from honest_design import read_hd
    from honest_design.validator import _impure_pure_functions

    module = read_hd(_SOURCE)["ok"]["modules"][0]
    actual = [fault["code"] for fault in _impure_pure_functions(module)]
    return [] if actual == _EXPECTED else [f"Expected {_EXPECTED!r}, received {actual!r}"]
