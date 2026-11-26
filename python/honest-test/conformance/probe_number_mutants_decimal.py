# scenario: _number_mutants keeps decimal token spans separate from unary signs
# inherits: hd=python/honest-test/honest-test.hd::_number_mutants -> feature=specs/features/honest-test.feature::_number_mutants keeps decimal token spans separate from unary signs
from tree_sitter import Point

from honest_test import parse_source
from honest_test.analyze import _number_mutants

_SOURCE = '000\n-1_000\n'
_EXPECTED = [
    {
        "location": f"{Point(0, 0)}-{Point(0, 3)}",
        "change_kind": "number_shift",
        "original": '000',
        "replacement": '1',
    },
    {
        "location": f"{Point(1, 1)}-{Point(1, 6)}",
        "change_kind": "number_shift",
        "original": '1_000',
        "replacement": '1001',
    },
]


def run() -> list[str]:
    actual = _number_mutants(parse_source(_SOURCE))
    if actual != _EXPECTED:
        return [f"expected {_EXPECTED!r}, got {actual!r}"]
    return []
