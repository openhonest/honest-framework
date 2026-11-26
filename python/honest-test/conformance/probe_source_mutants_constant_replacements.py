# scenario: source_mutants emits separate constant replacements in traversal order
# inherits: hd=python/honest-test/honest-test.hd::source_mutants -> feature=specs/features/honest-test.feature::source_mutants emits separate constant replacements in traversal order
"""Each constant replacement spans exactly one literal."""

from honest_parse import parse
from honest_test.analyze import source_mutants

from probe_source_mutants_condition_membership import _splice_if_original_matches

_SOURCE = b'zero = 0\none = 1\nyes = True\nno = False\nword = "text"\n'
_CASES = [
    ("0", "1", b'zero = 1\none = 1\nyes = True\nno = False\nword = "text"\n'),
    ("1", "0", b'zero = 0\none = 0\nyes = True\nno = False\nword = "text"\n'),
    ("True", "False", b'zero = 0\none = 1\nyes = False\nno = False\nword = "text"\n'),
    ("False", "True", b'zero = 0\none = 1\nyes = True\nno = True\nword = "text"\n'),
    ('"text"', '""', b'zero = 0\none = 1\nyes = True\nno = False\nword = ""\n'),
]


def probe_source_mutants_constant_replacements():
    tree = parse(_SOURCE, "python")
    mutations = source_mutants(tree.root_node)
    if not isinstance(mutations, list):
        return [f"source_mutants returned {mutations!r}, expected mutation records"]

    actual = [
        (mutant["original"], mutant["replacement"], _splice_if_original_matches(_SOURCE, mutant))
        for mutant in mutations
        if mutant["change_kind"] == "constant_replace"
    ]
    if actual != _CASES:
        return [f"constant_replace produced {actual!r}, expected {_CASES!r}"]
    return []


def run():
    failures = probe_source_mutants_constant_replacements()
    for failure in failures:
        print(failure)
    return len(failures)
