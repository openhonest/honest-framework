# scenario: enumerate_lengths generates no local cases for an unbounded upper range
# inherits: hd=python/honest-test/honest-test-pure.hd::enumerate_lengths -> feature=specs/features/honest-test.feature::enumerate_lengths generates no local cases for an unbounded upper range
"""Pure lower bounds must fall through to supplied values."""

from honest_parse import parse
from honest_test import enumerate_lengths

_EXPRESSIONS = ("len(s) >= 3", "len(s) > 3")
_EXPECTED = {"valid": [], "invalid": []}


def probe_enumerate_lengths_unbounded():
    failures = []
    for expression in _EXPRESSIONS:
        source = f"def candidate(s):\n    return {expression}\n".encode()
        tree = parse(source, "python")
        body = tree.root_node.named_children[0].child_by_field_name("body")
        actual = enumerate_lengths(body)
        if actual != _EXPECTED:
            failures.append(f"enumerate_lengths({expression!r}) returned {actual!r}, expected {_EXPECTED!r}")
    return failures


def run():
    failures = probe_enumerate_lengths_unbounded()
    for failure in failures:
        print(failure)
    return len(failures)
