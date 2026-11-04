"""Conformance fragment for the classify_predicate scenario (honest-test.feature).

Scenario: classify_predicate sorts one predicate into its generation class by
  analyzing its AST.
  Then it returns exactly one PredicateClass: numeric for int() or float() or a
  numeric comparison; length_bounded for a len(s) comparison; character_class for
  s.isdigit(), s.isalpha() or s.isupper(); external_lookup for a call to a function
  not defined in the codebase; composite for a call to a codebase-defined function,
  recursing into that callee at any depth; catch_all for a predicate that accepts
  nearly all inputs, already rejected at vocabulary construction by HC011.
  And the returned class picks the downstream generation strategy.
  And it reads no world and returns pure data.

Cases are data; one pure probe feeds them to the real pipeline and returns a list
of failure strings (empty when every case holds). No classes, no mocks. Each case
is a source snippet carrying one recognizer predicate whose body holds the marker
for a given class. The probe builds the input the way the runner does: it calls the
real honest_test.parse_source to parse the snippet, honest_test.extract_predicates
to pull the predicate node, and honest_test.classify_predicate to sort it.

The composite / external_lookup split turns on whether the called function is
defined in the same snippet, so the whole parsed tree is the input — which is why
the real parse_source and extract_predicates are used, not a hand-built node.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import classify_predicate, extract_predicates, parse_source

# Each snippet holds exactly one recognizer predicate. The marker in its body is the
# only thing that varies; the expected class is the one the scenario fixes for that
# marker. For composite the callee `double` is defined in the snippet as an ordinary
# helper; for external_lookup `in_registry` is never defined, so the codebase does
# not hold it.
_CASES = [
    # numeric: a numeric comparison with int().
    {
        "source": (
            "@recognizer\n"
            "def amount(s):\n"
            "    return int(s) > 0\n"
        ),
        "expect": "numeric",
    },
    # length_bounded: len(s) with a comparison operator.
    {
        "source": (
            "@recognizer\n"
            "def code(s):\n"
            "    return len(s) == 5\n"
        ),
        "expect": "length_bounded",
    },
    # character_class: s.isdigit().
    {
        "source": (
            "@recognizer\n"
            "def digits(s):\n"
            "    return s.isdigit()\n"
        ),
        "expect": "character_class",
    },
    # external_lookup: calls in_registry, which no def in this snippet provides.
    {
        "source": (
            "@recognizer\n"
            "def known(s):\n"
            "    return in_registry(s)\n"
        ),
        "expect": "external_lookup",
    },
    # composite: calls double, defined as an ordinary helper in the same snippet.
    {
        "source": (
            "def double(s):\n"
            "    return s + s\n"
            "\n"
            "@recognizer\n"
            "def twinned(s):\n"
            "    return double(s) == s + s\n"
        ),
        "expect": "composite",
    },
]


def probe_classify_predicate():
    """classify_predicate returns exactly the one PredicateClass the scenario fixes for each AST marker: numeric, length_bounded, character_class, external_lookup, composite."""
    bad = []
    for case in _CASES:
        tree = parse_source(case["source"])
        nodes = extract_predicates(tree)
        if len(nodes) != 1:
            bad.append(
                f"extract_predicates found {len(nodes)} predicate(s) in "
                f"{case['source']!r}, expected exactly 1 to classify"
            )
            continue
        got = classify_predicate(nodes[0])
        if got != case["expect"]:
            bad.append(
                f"classify_predicate({case['source']!r}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad


def run():
    bad = probe_classify_predicate()
    for line in bad:
        print(line)
    print(f"probe_classify_predicate: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
