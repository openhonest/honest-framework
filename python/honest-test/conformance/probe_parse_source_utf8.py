# scenario: parse_source returns a Python root for UTF-8 source
# inherits: hd=python/honest-test/honest-test.hd::parse_source -> feature=specs/features/honest-test.feature::parse_source returns a Python root for UTF-8 source
"""Verify that parse_source returns a Python root for UTF-8 source."""


def probe_parse_source_utf8():
    try:
        from honest_test.analyze import parse_source
    except ImportError as exc:
        return [f"cannot import parse_source: {exc}"]

    source = 'name = "café"\n'
    root = parse_source(source)
    if (root.type, root.text, root.has_error) != ("module", b'name = "caf\xc3\xa9"\n', False):
        return [f"parse_source returned {root!r}, expected a clean Python root over the UTF-8 source"]
    return []



def run():
    failures = probe_parse_source_utf8()
    for failure in failures:
        print(f"FAIL probe_parse_source_utf8: {failure}")
    return len(failures)
