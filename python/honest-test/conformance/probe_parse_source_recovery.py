# scenario: parse_source returns a recovered Python root for malformed source
# inherits: hd=python/honest-test/honest-test.hd::parse_source -> feature=specs/features/honest-test.feature::parse_source returns a recovered Python root for malformed source
"""Verify that parse_source returns a recovered Python root for malformed source."""


def probe_parse_source_recovery():
    try:
        from honest_test.analyze import parse_source
    except ImportError as exc:
        return [f"cannot import parse_source: {exc}"]

    from honest_parse import walk

    source = "def broken(:\n"
    root = parse_source(source)
    if root.type != "module" or root.text != source.encode("utf-8"):
        return [f"parse_source returned {root!r}, expected the original Python module root"]
    if not any(node.is_error or node.is_missing for node in walk(root)):
        return ["parse_source discarded the Python recovery descendants"]
    return []



def run():
    failures = probe_parse_source_recovery()
    for failure in failures:
        print(f"FAIL probe_parse_source_recovery: {failure}")
    return len(failures)
