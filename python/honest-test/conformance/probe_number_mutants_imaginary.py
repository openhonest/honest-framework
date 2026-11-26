# scenario: _number_mutants skips imaginary tokens and preserves integer order
# inherits: hd=python/honest-test/honest-test.hd::_number_mutants -> feature=specs/features/honest-test.feature::_number_mutants skips imaginary tokens and preserves integer order
from tree_sitter import Point

from honest_test import parse_source
from honest_test.analyze import _number_mutants

_SOURCE = '7\n2j\n3J\n9\n'
_EXPECTED = [
    {
        "location": f"{Point(0, 0)}-{Point(0, 1)}",
        "change_kind": "number_shift",
        "original": '7',
        "replacement": '8',
    },
    {
        "location": f"{Point(3, 0)}-{Point(3, 1)}",
        "change_kind": "number_shift",
        "original": '9',
        "replacement": '10',
    },
]


def run() -> list[str]:
    actual = _number_mutants(parse_source(_SOURCE))
    if actual != _EXPECTED:
        return [f"expected {_EXPECTED!r}, got {actual!r}"]
    return []
