# scenario: _reserved_field accepts is_err on the Fault record
# inherits: hd=python/honest-design/honest-design.hd::_reserved_field -> feature=python/honest-design/features/honest-design.feature::_reserved_field accepts is_err on the Fault record

_SOURCE = (
    'module example\n'
    '  type Fault = { is_err: bool\n'
    ' code: str }\n'
)
_EXPECTED = []


def probe_reserved_field_fault_record():
    from honest_design import read_hd
    from honest_design.validator import _reserved_field

    module = read_hd(_SOURCE)["ok"]["modules"][0]
    faults = _reserved_field(module)
    return [] if faults == _EXPECTED else [f"Expected no diagnostics, received {faults!r}"]
