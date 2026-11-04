"""Conformance fragment for the parse_source scenario (honest-test.feature ~line 122).

Scenario: parse_source parses one source file with tree-sitter and returns the
  root node.
  Then it returns the tree's root node, which extract_predicates walks for
  predicate nodes and mutate_source walks for the spans each change sits at.
  And the parse is deterministic and reads no world.
  And tree-sitter produces a tree with error nodes for malformed input rather
  than failing, so it returns a node, never a fault.

Cases are data; one pure probe feeds a Python source STRING to the real
honest_test.parse_source and returns a list of failure strings (empty when
every case holds). No classes, no mocks, no hand-built tree-sitter Node: the
probe calls the real function and reads structural properties off its result.

The source analyzed is Python source — honest-test parses the recognizer
predicates a module declares. The valid case is a well-formed predicate; the
malformed case breaks Python syntax so the tree carries an error.

This is its own fragment file so the other scenarios' fragments never collide
with it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import parse_source

# A well-formed Python recognizer predicate. tree-sitter parses it cleanly, so
# the root node reports no error.
_VALID_SOURCE = "def is_short(s):\n    return len(s) <= 10\n"

# Malformed Python: the def line is missing its colon and the len( call is never
# closed. tree-sitter does not raise; it returns a tree whose root reports an
# error. The scenario fixes this behaviour: a node, never a fault.
_MALFORMED_SOURCE = "def is_short(s)\n    return len(s <= 10\n"

_CASES = [
    # Valid source: a node comes back, it carries no parse error. has_error is
    # the literal, non-trivial expected output the scenario fixes (False here,
    # True below); a stub lacking the attribute cannot satisfy either side.
    {
        "name": "valid predicate source",
        "source": _VALID_SOURCE,
        "expect_has_error": False,
    },
    # Malformed source: a node still comes back (no raise), and it reports an
    # error rather than failing. This is the scenario's absence-of-fault case.
    {
        "name": "malformed source",
        "source": _MALFORMED_SOURCE,
        "expect_has_error": True,
    },
]


def probe_parse_source():
    """parse_source returns the tree's walkable root node for any Python source, reporting a parse error for malformed input instead of raising a fault."""
    bad = []
    for case in _CASES:
        src = case["source"]
        try:
            node = parse_source(src)
        except Exception as exc:  # the scenario says it never fails, even on malformed input
            bad.append(
                f"parse_source({case['name']}) raised {type(exc).__name__}: {exc}; "
                f"expected a node, never a raise"
            )
            continue

        # (a) a node comes back, never None.
        if node is None:
            bad.append(f"parse_source({case['name']}) returned None, expected a node")
            continue

        # (b) the node is the walkable root extract_predicates and mutate_source
        # read: it exposes a type and children. (The exact attribute names are
        # tree-sitter's; see GAPS.)
        for attr in ("type", "children"):
            if not hasattr(node, attr):
                bad.append(
                    f"parse_source({case['name']}) -> node lacking .{attr}; "
                    f"not a walkable tree-sitter root node"
                )

        # (c) the error-node property the scenario fixes: no error for valid
        # source, an error for malformed source, and in neither case a raise.
        if not hasattr(node, "has_error"):
            bad.append(
                f"parse_source({case['name']}) -> node lacking .has_error; "
                f"cannot tell a clean parse from one carrying error nodes"
            )
            continue
        if bool(node.has_error) != case["expect_has_error"]:
            bad.append(
                f"parse_source({case['name']}).has_error is {bool(node.has_error)}, "
                f"expected {case['expect_has_error']}"
            )
    return bad


def run():
    bad = probe_parse_source()
    for line in bad:
        print(line)
    print(f"probe_parse_source: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
