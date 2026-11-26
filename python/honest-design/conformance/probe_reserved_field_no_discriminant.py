# scenario: _reserved_field accepts records without is_err
# inherits: hd=python/honest-design/honest-design.hd::_reserved_field -> feature=python/honest-design/features/honest-design.feature::_reserved_field accepts records without is_err

_SOURCE = (
    'module example\n'
    '  type Result = { value: int }\n'
    '  type Receipt = { id: str }\n'
)
_EXPECTED = []


def probe_reserved_field_no_discriminant():
    from honest_design import read_hd
    from honest_design.validator import _reserved_field

    module = read_hd(_SOURCE)["ok"]["modules"][0]
    faults = _reserved_field(module)
    return [] if faults == _EXPECTED else [f"Expected no diagnostics, received {faults!r}"]
