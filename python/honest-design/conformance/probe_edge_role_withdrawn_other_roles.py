# scenario: _edge_role_withdrawn accepts the other supported roles
# inherits: hd=python/honest-design/honest-design.hd::_edge_role_withdrawn -> feature=python/honest-design/features/honest-design.feature::_edge_role_withdrawn accepts the other supported roles

_SOURCE = (
    'module example\n'
    '  orchestrator fn run : (key: str) -> str note "coordinates work"\n'
    '  fn choose : (key: str) -> str note "selects a key"\n'
    '  boundary_out fn publish : (key: str) -> str note "publishes a key"\n'
)
_EXPECTED = []


def probe_edge_role_withdrawn_other_roles():
    from honest_design import read_hd
    from honest_design.validator import _edge_role_withdrawn

    module = read_hd(_SOURCE)["ok"]["modules"][0]
    faults = _edge_role_withdrawn(module)
    return [] if faults == _EXPECTED else [f"Expected no diagnostics, received {faults!r}"]
