# scenario: _number_mutants shifts hexadecimal octal and binary tokens
# inherits: hd=python/honest-test/honest-test.hd::_number_mutants -> feature=specs/features/honest-test.feature::_number_mutants shifts hexadecimal octal and binary tokens
from tree_sitter import Point

from honest_test import parse_source
from honest_test.analyze import _number_mutants

_SOURCE = '0x0FFF\n0O_17\n0B_11\n'
_EXPECTED = [
    {
        "location": f"{Point(0, 0)}-{Point(0, 6)}",
        "change_kind": "number_shift",
        "original": '0x0FFF',
        "replacement": '4096',
    },
    {
        "location": f"{Point(1, 0)}-{Point(1, 5)}",
        "change_kind": "number_shift",
        "original": '0O_17',
        "replacement": '16',
    },
    {
        "location": f"{Point(2, 0)}-{Point(2, 5)}",
        "change_kind": "number_shift",
        "original": '0B_11',
        "replacement": '4',
    },
]


def run() -> list[str]:
    actual = _number_mutants(parse_source(_SOURCE))
    if actual != _EXPECTED:
        return [f"expected {_EXPECTED!r}, got {actual!r}"]
    return []
