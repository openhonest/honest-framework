# scenario: source_mutants returns a fault for an unparseable root
# inherits: hd=python/honest-test/honest-test.hd::source_mutants -> feature=specs/features/honest-test.feature::source_mutants returns a fault for an unparseable root
"""Verify that source_mutants returns a fault for an unparseable root."""


def probe_source_mutants_malformed():
    try:
        from honest_test.analyze import source_mutants
    except ImportError as exc:
        return [f"cannot import source_mutants: {exc}"]

    from honest_parse import parse

    tree = parse(b"def broken(:\n", "python")
    got = source_mutants(tree.root_node)
    if not isinstance(got, dict) or got.keys() != {"problem", "remedy"}:
        return [f"source_mutants returned {got!r}, expected a Fault"]
    if "parse" not in got["problem"] or "fix" not in got["remedy"]:
        return [f"source_mutants returned {got!r}, expected parse failure with a correction"]
    return []



def run():
    failures = probe_source_mutants_malformed()
    for failure in failures:
        print(f"FAIL probe_source_mutants_malformed: {failure}")
    return len(failures)
