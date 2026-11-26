# scenario: source_mutants emits separate condition and membership changes in traversal order
# inherits: hd=python/honest-test/honest-test.hd::source_mutants -> feature=specs/features/honest-test.feature::source_mutants emits separate condition and membership changes in traversal order
"""Every mutation changes one site while preserving both operands and all other lines."""

import re

from honest_parse import parse
from honest_test.analyze import source_mutants

_SOURCE = b"left = a and b\nright = c or d\nfirst = p in group\nsecond = q in other\n"
_CONDITIONS = [
    b"left = a or b\nright = c or d\nfirst = p in group\nsecond = q in other\n",
    b"left = a and b\nright = c and d\nfirst = p in group\nsecond = q in other\n",
]
_MEMBERSHIPS = [
    b"left = a and b\nright = c or d\nfirst = p not in group\nsecond = q in other\n",
    b"left = a and b\nright = c or d\nfirst = p in group\nsecond = q not in other\n",
]
_SPAN = re.compile(r"Point\(row=(\d+), column=(\d+)\)-Point\(row=(\d+), column=(\d+)\)")


def _splice_if_original_matches(source, mutant):
    """Use the reported tree-sitter positions directly, without the mutation harness."""
    match = _SPAN.fullmatch(mutant["location"])
    if match is None:
        return None
    first_row, first_column, last_row, last_column = map(int, match.groups())
    lines = source.splitlines(keepends=True)
    if max(first_row, last_row) >= len(lines):
        return None
    start = sum(map(len, lines[:first_row])) + first_column
    stop = sum(map(len, lines[:last_row])) + last_column
    if not 0 <= start < stop <= len(source) or source[start:stop] != mutant["original"].encode():
        return None
    return source[:start] + mutant["replacement"].encode() + source[stop:]


def probe_source_mutants_condition_membership():
    tree = parse(_SOURCE, "python")
    mutations = source_mutants(tree.root_node)
    if not isinstance(mutations, list):
        return [f"source_mutants returned {mutations!r}, expected mutation records"]

    failures = []
    for kind, expected in (("condition_flip", _CONDITIONS), ("membership_change", _MEMBERSHIPS)):
        records = [mutant for mutant in mutations if mutant["change_kind"] == kind]
        spliced = [_splice_if_original_matches(_SOURCE, mutant) for mutant in records]
        if spliced != expected:
            failures.append(f"{kind} produced {spliced!r}, expected {expected!r}; records: {records!r}")
    return failures


def run():
    failures = probe_source_mutants_condition_membership()
    for failure in failures:
        print(failure)
    return len(failures)
