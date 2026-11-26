# scenario: _membership_mutants ignores iterator syntax strings and comments
# inherits: hd=python/honest-test/honest-test.hd::_membership_mutants -> feature=specs/features/honest-test.feature::_membership_mutants ignores iterator syntax strings and comments

from honest_parse import parse

from probe_source_mutants_condition_membership import _splice_if_original_matches

_SOURCE = b"items = [a for a in b]\nfor a in b:\n    pass\ntext = 'a in b not in c'\n# in and not in\n"
_EXPECTED = []
_SPLICED = []


def probe_membership_mutants_exclusions():
    try:
        from honest_test.analyze import _membership_mutants
    except ImportError as error:
        return [f"cannot import _membership_mutants: {error}"]

    root = parse(_SOURCE, "python").root_node
    actual = _membership_mutants(root)
    expected = [
        {
            "location": f"Point(row=0, column={start})-Point(row=0, column={end})",
            "change_kind": "membership_change",
            "original": original,
            "replacement": replacement,
        }
        for start, end, original, replacement in _EXPECTED
    ]
    if actual != expected:
        return [f"membership records {actual!r}, expected {expected!r}"]
    spliced = [_splice_if_original_matches(_SOURCE, mutation) for mutation in actual]
    if spliced != _SPLICED:
        return [f"membership splices {spliced!r}, expected {_SPLICED!r}"]
    return []


def run():
    failures = probe_membership_mutants_exclusions()
    for failure in failures:
        print(failure)
    return len(failures)
