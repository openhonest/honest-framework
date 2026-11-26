# scenario: _held_not_read faults a legacy edge that names an alias leading to handle
# inherits: hd=python/honest-design/honest-design.hd::_held_not_read -> feature=python/honest-design/features/honest-design.feature::_held_not_read faults a legacy edge that names an alias leading to handle

_SOURCE = (
    'module example\n'
    '  type Catalog = handle\n'
    '  type Source = Catalog\n'
    '  edge fn find : (catalog: Source) -> str note "finds a value"\n'
)
_EXPECTED = ['handle_read']


def probe_held_not_read_legacy_edge_alias():
    from honest_design import read_hd
    from honest_design.validator import _held_not_read

    module = read_hd(_SOURCE)["ok"]["modules"][0]
    actual = [fault["code"] for fault in _held_not_read(module)]
    return [] if actual == _EXPECTED else [f"Expected {_EXPECTED!r}, received {actual!r}"]
