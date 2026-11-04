"""Conformance fragment for the extract_predicates scenario (honest-test.feature).

Scenario: extract_predicates walks a parsed tree and returns each recognizer
  predicate node.
  Then it returns one node per predicate found, each the body honest-test analyzes.
  And an empty list means the file declares no predicates.
  And it reads no world and returns pure data.

The input is built by the REAL pipeline, never hand-constructed: parse_source turns
a Python source snippet into a tree-sitter tree, and extract_predicates walks that
tree. A recognizer predicate appears in source as a callable passed to honest-type's
predicate(...) (honest-type-architecture.md §2, the Detection column analyzes the
predicate body: len(s), s.isdigit(), int(s)). A Set recognizer contributes no
predicate (§3.2), so a Set-only vocabulary declares none.

Cases are data; one pure probe feeds them to the real functions and returns a list
of failure strings (empty when every case holds). No classes, no mocks.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import extract_predicates, parse_source

_CASES = [
    # Two recognizer predicates, each a lambda passed to predicate(). A stub that
    # returns [] fails this: the count literal 2 is written out, not computed.
    {
        "source": (
            "from honest_type import vocabulary, predicate\n"
            "\n"
            "vocab = vocabulary({\n"
            '    "short":  predicate(lambda s: len(s) <= 10),\n'
            '    "digits": predicate(lambda s: s.isdigit()),\n'
            "})\n"
        ),
        "expect_count": 2,
    },
    # One recognizer predicate.
    {
        "source": (
            "from honest_type import vocabulary, predicate\n"
            "\n"
            'vocab = vocabulary({"small": predicate(lambda s: int(s) < 100)})\n'
        ),
        "expect_count": 1,
    },
    # The explicit absence case: a Set-only vocabulary declares no predicate, so
    # extract_predicates returns the empty list.
    {
        "source": (
            "from honest_type import vocabulary\n"
            "\n"
            'vocab = vocabulary({"color": {"red", "green", "blue"}})\n'
        ),
        "expect_count": 0,
    },
]


def _is_tree_node(item):
    """A tree-sitter node, not a string: it carries a `type` attribute and is not str."""
    return not isinstance(item, str) and hasattr(item, "type")


def probe_extract_predicates():
    """extract_predicates returns one tree-sitter node per recognizer predicate in the source, and the empty list when the source declares none."""
    bad = []
    for case in _CASES:
        tree = parse_source(case["source"])
        got = extract_predicates(tree)
        if len(got) != case["expect_count"]:
            bad.append(
                f"extract_predicates(parse_source(...)) returned {len(got)} nodes, "
                f"expected {case['expect_count']} for source:\n{case['source']}"
            )
            continue
        non_nodes = [item for item in got if not _is_tree_node(item)]
        if non_nodes:
            bad.append(
                f"extract_predicates returned non-node items {non_nodes!r} "
                f"(expected tree-sitter nodes) for source:\n{case['source']}"
            )
    return bad


def run():
    bad = probe_extract_predicates()
    for line in bad:
        print(line)
    print(f"probe_extract_predicates: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
