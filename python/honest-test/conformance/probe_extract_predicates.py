"""RED probe for honest-test.extract_predicates — the predicate-node finder (.hd, spec section 2).

extract_predicates walks a parsed source tree and returns one node per recognizer
predicate the file declares — the body each predicate strategy then analyzes. A file
declaring no recognizers yields the empty list. Recognizers are marked `@recognizer`
(spec sections 1, 8.3); a plain function or a `@link` is not a recognizer predicate and
is not returned. It reads no world and returns pure data.
honest-test has no code yet, so importing honest_test fails — the correct red state.
"""

from honest_test import extract_predicates, parse_source


def _predicate_nodes(source):
    """Parse source and return extract_predicates' node list for it."""
    return extract_predicates(parse_source(source))


def probe_extract_predicates():
    """extract_predicates returns one node per `@recognizer`-marked predicate, the empty
    list when the file declares none, and ignores plain functions and `@link`s."""
    bad = []

    three = (
        "@recognizer\n"
        "def is_five(s):\n"
        "    return len(s) == 5\n"
        "\n"
        "@recognizer\n"
        "def is_digits(s):\n"
        "    return s.isdigit()\n"
        "\n"
        "@recognizer\n"
        "def is_positive(s):\n"
        "    return int(s) > 0\n"
    )
    nodes = _predicate_nodes(three)
    if not isinstance(nodes, list):
        bad.append(f"extract_predicates returned {type(nodes).__name__}, expected a list of nodes")
    elif len(nodes) != 3:
        bad.append(f"a file with three recognizers must yield 3 predicate nodes, got {len(nodes)}")

    # A file with no recognizer predicate yields the empty list.
    empty = _predicate_nodes("x = 1\n\ndef helper(a, b):\n    return a + b\n")
    if empty != []:
        bad.append(f"a file declaring no recognizer must yield [], got {empty!r}")

    # Only `@recognizer` predicates count: a plain function and a `@link` are excluded.
    mixed = (
        "@recognizer\n"
        "def is_name(s):\n"
        "    return s.isalpha()\n"
        "\n"
        "@link\n"
        "def format_name(m):\n"
        "    return m\n"
        "\n"
        "def plain(s):\n"
        "    return len(s) == 3\n"
    )
    mixed_nodes = _predicate_nodes(mixed)
    if len(mixed_nodes) != 1:
        bad.append(
            f"only the one `@recognizer` must be returned, not the `@link` or the plain def; got {len(mixed_nodes)}"
        )

    return bad


def run():
    failures = probe_extract_predicates()
    for message in failures:
        print(f"FAIL extract_predicates: {message}")
    print(f"extract_predicates probe: {'PASS' if not failures else str(len(failures)) + ' failed'}")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)
