"""pair_source joins one discovered path with its already-read text into a
SourceFile record and returns it, deciding nothing.

Pins the function contract: the returned record carries the path and the text it
was handed, unchanged. A stub returning {} carries neither and fails this probe.
"""

# One ordinary case pins both fields to literal inputs. There is no absence case:
# pair_source takes two plain strings and always returns a record of exactly them.
_CASES = [
    {"given": {"path": "a.py", "text": "x = 1"}, "expect": {"path": "a.py", "text": "x = 1"}},
    {"given": {"path": "src/pkg/mod.py", "text": ""}, "expect": {"path": "src/pkg/mod.py", "text": ""}},
]


def probe_pair_source():
    try:
        from honest_check import pair_source
    except ImportError as exc:
        return [f"cannot import pair_source: {exc}"]

    bad = []
    for case in _CASES:
        got = pair_source(**case["given"])
        if not isinstance(got, dict):
            bad.append(f"pair_source({case['given']}) -> {got!r}, expected a record")
            continue
        if got.get("path") != case["expect"]["path"] or got.get("text") != case["expect"]["text"]:
            bad.append(
                f"pair_source({case['given']}) -> {got!r}, expected {case['expect']!r}"
            )
    return bad
