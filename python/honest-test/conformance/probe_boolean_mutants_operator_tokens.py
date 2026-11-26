# scenario: _boolean_mutants flips only operator tokens in source order
# inherits: hd=python/honest-test/honest-test.hd::_boolean_mutants -> feature=specs/features/honest-test.feature::_boolean_mutants flips only operator tokens in source order
"""Check token byte spans and preserve all surrounding source."""

from honest_parse import parse

from probe_source_mutants_condition_membership import _splice_if_original_matches

_SOURCE = b"result: bool = (a and b) or c # and in a comment\n"
_EXPECTED = [
    {
        "location": "Point(row=0, column=18)-Point(row=0, column=21)",
        "change_kind": "condition_flip",
        "original": "and",
        "replacement": "or",
    },
    {
        "location": "Point(row=0, column=25)-Point(row=0, column=27)",
        "change_kind": "condition_flip",
        "original": "or",
        "replacement": "and",
    },
]
_SPLICED = [
    b"result: bool = (a or b) or c # and in a comment\n",
    b"result: bool = (a and b) and c # and in a comment\n",
]


def probe_boolean_mutants_operator_tokens():
    try:
        from honest_test.analyze import _boolean_mutants
    except ImportError as exc:
        return [f"cannot import _boolean_mutants: {exc}"]

    tree = parse(_SOURCE, "python")
    actual = _boolean_mutants(tree.root_node)
    if actual != _EXPECTED:
        return [f"_boolean_mutants returned {actual!r}, expected {_EXPECTED!r}"]
    spliced = [_splice_if_original_matches(_SOURCE, mutant) for mutant in actual]
    if spliced != _SPLICED:
        return [f"operator tokens produced {spliced!r}, expected {_SPLICED!r}"]
    return []


def run():
    failures = probe_boolean_mutants_operator_tokens()
    for failure in failures:
        print(failure)
    return len(failures)
