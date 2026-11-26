# scenario: _boolean_mutants returns no flips for operator words in strings and comments
# inherits: hd=python/honest-test/honest-test.hd::_boolean_mutants -> feature=specs/features/honest-test.feature::_boolean_mutants returns no flips for operator words in strings and comments
"""Literal and comment text contains no Boolean operator tokens."""

from honest_parse import parse

_SOURCE = b'words = "and or" # and or\n'


def probe_boolean_mutants_no_tokens():
    try:
        from honest_test.analyze import _boolean_mutants
    except ImportError as exc:
        return [f"cannot import _boolean_mutants: {exc}"]

    tree = parse(_SOURCE, "python")
    actual = _boolean_mutants(tree.root_node)
    if actual != []:
        return [f"_boolean_mutants returned {actual!r} for a literal and comment, expected []"]
    return []


def run():
    failures = probe_boolean_mutants_no_tokens()
    for failure in failures:
        print(failure)
    return len(failures)
