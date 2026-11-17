"""RED probe for honest-test.classify_predicate — the predicate classifier (.hd, spec section 2).

classify_predicate reads one predicate node for the markers that decide its generation
class and returns exactly one PredicateClass. From the node alone it decides the three
source-decidable classes: an int()/float() call or a numeric comparison is numeric, a
len(s) comparison is length_bounded, and s.isdigit()/s.isalpha()/s.isupper() is
character_class. It reads no world and returns pure data.
honest-test has no code yet, so importing honest_test fails — the correct red state.

(external_lookup and composite turn on whether a called function is defined in the
codebase, which the single-node signature cannot see, so they are not probed here.)
"""

from honest_test import classify_predicate, extract_predicates, parse_source


def _one_predicate_node(source):
    """Parse source with exactly one recognizer and return its predicate node, or a
    message when the pipeline did not yield exactly one node."""
    nodes = extract_predicates(parse_source(source))
    if not isinstance(nodes, list) or len(nodes) != 1:
        return None, f"expected exactly one predicate node, got {nodes!r}"
    return nodes[0], None


def probe_classify_predicate():
    """classify_predicate returns 'numeric' for a numeric comparison, 'length_bounded'
    for a len(s) comparison, and 'character_class' for an is-method call."""
    bad = []

    cases = [
        ("@recognizer\ndef is_positive(s):\n    return int(s) > 0\n", "numeric"),
        ("@recognizer\ndef is_five(s):\n    return len(s) == 5\n", "length_bounded"),
        ("@recognizer\ndef is_digits(s):\n    return s.isdigit()\n", "character_class"),
        ("@recognizer\ndef is_alpha(s):\n    return s.isalpha()\n", "character_class"),
    ]

    for source, expected in cases:
        node, err = _one_predicate_node(source)
        if err:
            bad.append(err)
            continue
        got = classify_predicate(node)
        if got != expected:
            bad.append(f"classify_predicate for {expected!r} source returned {got!r}")

    return bad


def run():
    failures = probe_classify_predicate()
    for message in failures:
        print(f"FAIL classify_predicate: {message}")
    print(f"classify_predicate probe: {'PASS' if not failures else str(len(failures)) + ' failed'}")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)
