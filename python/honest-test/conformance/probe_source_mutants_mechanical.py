# scenario: source_mutants enumerates the declared mechanical changes
# inherits: hd=python/honest-test/honest-test.hd::source_mutants -> feature=specs/features/honest-test.feature::source_mutants enumerates the declared mechanical changes
"""Verify that source_mutants enumerates the declared mechanical changes."""


def probe_source_mutants_mechanical():
    try:
        from honest_test.analyze import source_mutants
    except ImportError as exc:
        return [f"cannot import source_mutants: {exc}"]

    from honest_parse import parse

    tree = parse(
        b"left < right\nleft <= right\nleft > right\nleft >= right\nleft == right\nleft != right\n",
        "python",
    )
    actual = source_mutants(tree.root_node)
    expected = [
        {
            "change_kind": "comparison_swap",
            "original": original,
            "replacement": replacement,
            "location": f"Point(row={row}, column=5)-Point(row={row}, column={end})",
        }
        for row, (original, replacement, end) in enumerate([
            ("<", "<=", 6),
            ("<=", "<", 7),
            (">", ">=", 6),
            (">=", ">", 7),
            ("==", "!=", 7),
            ("!=", "==", 7),
        ])
    ]
    if actual != expected:
        return [f"source_mutants returned {actual!r}, expected comparison swaps {expected!r}"]
    return []



def run():
    failures = probe_source_mutants_mechanical()
    for failure in failures:
        print(f"FAIL probe_source_mutants_mechanical: {failure}")
    return len(failures)
