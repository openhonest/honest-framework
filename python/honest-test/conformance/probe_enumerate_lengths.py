"""RED probe for honest-test.enumerate_lengths — the length-bounded generator (.hd, spec section 3.4).

enumerate_lengths reads the minimum and maximum length from a predicate's comparison
operators and returns a LengthCases: one valid string at every length in the range, and
the invalid boundary lengths just outside — one over the maximum always, and one under
the minimum when the minimum exceeds one. Valid strings are built from
"abcdefghijklmnopqrstuvwxyz0123456789" sliced to the wanted length. A pure lower bound
with no maximum is unbounded above and generates nothing here, falling to supplied
values. It reads no world and returns pure data.
honest-test has no code yet, so importing honest_test fails — the correct red state.
"""

from honest_test import enumerate_lengths, extract_predicates, parse_source

_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789"


def _s(n):
    """The length-n string enumerate_lengths builds: the alphabet sliced to n (n <= 36 here)."""
    return _CHARS[:n]


def _one_predicate_node(source):
    nodes = extract_predicates(parse_source(source))
    if not isinstance(nodes, list) or len(nodes) != 1:
        return None, f"expected exactly one predicate node, got {nodes!r}"
    return nodes[0], None


def probe_enumerate_lengths():
    """enumerate_lengths reads the operator to fix the bounds, enumerates every valid
    length, and places the symmetric boundary lengths — one over the maximum always, one
    under the minimum only when the minimum exceeds one."""
    bad = []

    cases = [
        # (source body, expected valid, expected invalid) — invalid order: over, then under.
        ("len(s) == 5", [_s(5)], [_s(6), _s(4)]),
        ("len(s) <= 8", [_s(n) for n in range(1, 9)], [_s(9)]),
        ("len(s) < 8", [_s(n) for n in range(1, 8)], [_s(8)]),
        ("3 <= len(s) <= 8", [_s(n) for n in range(3, 9)], [_s(9), _s(2)]),
        # A pure lower bound with no maximum generates nothing here.
        ("len(s) >= 3", [], []),
    ]

    for body, want_valid, want_invalid in cases:
        source = f"@recognizer\ndef r(s):\n    return {body}\n"
        node, err = _one_predicate_node(source)
        if err:
            bad.append(f"{body!r}: {err}")
            continue
        got = enumerate_lengths(node)
        if not isinstance(got, dict):
            bad.append(f"{body!r}: enumerate_lengths returned {type(got).__name__}, expected a LengthCases dict")
            continue
        if got.get("valid") != want_valid:
            bad.append(f"{body!r}: valid = {got.get('valid')!r}, expected {want_valid!r}")
        if got.get("invalid") != want_invalid:
            bad.append(f"{body!r}: invalid = {got.get('invalid')!r}, expected {want_invalid!r}")

    return bad


def run():
    failures = probe_enumerate_lengths()
    for message in failures:
        print(f"FAIL enumerate_lengths: {message}")
    print(f"enumerate_lengths probe: {'PASS' if not failures else str(len(failures)) + ' failed'}")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)
