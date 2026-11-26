# scenario: classify_predicate selects generation classes for declared syntax markers
# inherits: hd=python/honest-test/honest-test-pure.hd::classify_predicate -> feature=specs/features/honest-test.feature::classify_predicate selects generation classes for declared syntax markers
"""Verify declared classification markers and length comparison precedence."""

from honest_parse import parse
from honest_test import classify_predicate

_CASES = [
    ("int(s)", "numeric"),
    ("float(s)", "numeric"),
    ("s > 1", "numeric"),
    ("s > 1.5", "numeric"),
    ("1e3 < s", "numeric"),
    ("len(s) < 5", "length_bounded"),
    ("len(s) < 1.5", "length_bounded"),
    ("s.isdigit()", "character_class"),
    ("s.isalpha()", "character_class"),
    ("s.isupper()", "character_class"),
    ("external_lookup_api(s)", "external_lookup"),
    ("external_lookup_api(s) > threshold", "external_lookup"),
]


def probe_classify_predicate_declared_markers():
    failures = []
    for expression, expected in _CASES:
        source = f"def candidate(s):\n    return {expression}\n".encode()
        tree = parse(source, "python")
        body = tree.root_node.named_children[0].child_by_field_name("body")
        actual = classify_predicate(body)
        if actual != expected:
            failures.append(f"classify_predicate({expression!r}) returned {actual!r}, expected {expected!r}")
    return failures


def run():
    failures = probe_classify_predicate_declared_markers()
    for failure in failures:
        print(failure)
    return len(failures)
