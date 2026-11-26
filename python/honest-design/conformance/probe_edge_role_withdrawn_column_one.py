# scenario: _edge_role_withdrawn accepts reader and boundary_in in column 1
# inherits: hd=python/honest-design/honest-design.hd::_edge_role_withdrawn -> feature=python/honest-design/features/honest-design.feature::_edge_role_withdrawn accepts reader and boundary_in in column 1

_SOURCE = (
    'module example\n'
    '  reader fn read_value : (key: str) -> str note "reads a value"\n'
    '  boundary_in fn request : (key: str) -> str note "receives a request"\n'
)
_EXPECTED = []


def probe_edge_role_withdrawn_column_one():
    from honest_design import read_hd
    from honest_design.validator import _edge_role_withdrawn

    module = read_hd(_SOURCE)["ok"]["modules"][0]
    faults = _edge_role_withdrawn(module)
    return [] if faults == _EXPECTED else [f"Expected no diagnostics, received {faults!r}"]
