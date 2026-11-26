# scenario: extract_predicates selects recognizers from a mixed source file
# inherits: hd=python/honest-test/honest-test.hd::extract_predicates -> feature=specs/features/honest-test.feature::extract_predicates selects recognizers from a mixed source file
"""The two returned predicate nodes belong only to the recognizers."""

from honest_parse import parse
from honest_test import extract_predicates

_SOURCE = b"""def plain(s):
    return s

@recognizer
def first(s):
    return s.isalpha()

@link
def step(manifest):
    return manifest

@recognizer
def second(s):
    return s.isdigit()
"""
_EXPECTED_NAMES = [b"first", b"second"]


def probe_extract_predicates_mixed():
    tree = parse(_SOURCE, "python")
    actual = extract_predicates(tree.root_node)
    names = []
    for node in actual:
        function = node if node.type == "function_definition" else node.parent
        if function is None or function.type != "function_definition":
            return [f"extract_predicates returned a node outside a recognizer function: {node!r}"]
        body = function.child_by_field_name("body")
        if node != function and node != body:
            return [f"extract_predicates returned neither the recognizer declaration nor its body: {node!r}"]
        names.append(function.child_by_field_name("name").text)
    if sorted(names) != _EXPECTED_NAMES:
        return [f"extract_predicates returned {names!r}, expected nodes for {_EXPECTED_NAMES!r}"]
    return []


def run():
    failures = probe_extract_predicates_mixed()
    for failure in failures:
        print(failure)
    return len(failures)
