"""Conformance fragment for the encoding_variants scenario (honest-test.feature).

Scenario: encoding_variants generates the encoding-variant neighbor class.
  Then it returns value with a UTF-16 byte-order-mark prefix, an overlong UTF-8
  encoding of its ASCII, a double percent-encoding, a mixed UTF-8 and latin-1
  encoding, and whitespace-normalization attacks that replace a space with a
  non-breaking space or a line separator.
  And these target recognizers that accept after normalization rather than
  rejecting malformed input.
  And it reads no world and returns pure data.

Cases are data; one pure probe feeds them to the real function and returns a list
of failure strings (empty when every case holds). No classes, no mocks: it calls
the real honest_test.encoding_variants.

The .hd declares the return element type as str, so every structural assertion is
made against the str form the function returns. The exact byte forms the neighbors
carry are implementation detail; structure is not. This is its own fragment file
so the other scenarios' fragments never collide with it.
"""

from honest_test import encoding_variants

# U+FEFF, the zero-width no-break space that is the str form of a UTF-16 BOM.
_BOM = "﻿"
# The two whitespace-normalization substitutes named in the note.
_NBSP = " "  # non-breaking space
_LINE_SEP = " "  # line separator

_CASES = [
    # A value with a space and ASCII letters exercises every one of the five
    # named classes, including the whitespace-normalization attack on its space.
    {"given": {"value": "a b"}, "has_space": True},
    # A value with no space: the whitespace-normalization variants must be absent,
    # while the byte-order-mark class still fires.
    {"given": {"value": "ab"}, "has_space": False},
]


def _has_whitespace_variant(neighbors):
    """True when some neighbor introduces a non-breaking space or a line separator."""
    return any((_NBSP in n) or (_LINE_SEP in n) for n in neighbors)


def probe_encoding_variants():
    """encoding_variants returns a non-empty neighbor list carrying a UTF-16 BOM prefix, a double percent-encoding, and a whitespace-normalization substitute exactly when the value has a space."""
    bad = []
    for case in _CASES:
        value = case["given"]["value"]
        got = encoding_variants(value)

        # (a) the neighbor list is non-empty. A stub returning [] dies here.
        if not got:
            bad.append(
                f"encoding_variants({value!r}) produced an empty list, "
                f"expected the encoding-variant neighbor class"
            )
            continue

        # (b) at least one neighbor begins with a UTF-16 byte-order-mark.
        if not any(n.startswith(_BOM) for n in got):
            bad.append(
                f"encoding_variants({value!r}) -> {got}, "
                f"expected at least one neighbor beginning with a UTF-16 BOM ({_BOM!r})"
            )

        # (d)/absence: the whitespace-normalization variant is present exactly
        # when the value has a space to normalize.
        present = _has_whitespace_variant(got)
        if case["has_space"] and not present:
            bad.append(
                f"encoding_variants({value!r}) -> {got}, "
                f"expected a neighbor replacing the space with {_NBSP!r} or {_LINE_SEP!r}"
            )
        if not case["has_space"] and present:
            bad.append(
                f"encoding_variants({value!r}) -> {got}, "
                f"expected no whitespace-normalization variant for a value with no space"
            )

        # The space-bearing value also pins the double-percent-encoding class and
        # the all-neighbors-differ claim; a value of only unreserved ASCII letters
        # percent-encodes to itself, so those two are asserted only here.
        if case["has_space"]:
            # (c) a double percent-encoding is present: the space's %20 re-encoded
            # to %2520 carries the literal "%25".
            if not any("%25" in n for n in got):
                bad.append(
                    f"encoding_variants({value!r}) -> {got}, "
                    f"expected a double percent-encoded neighbor containing '%25'"
                )
            # (e) every neighbor differs from the input.
            same = [n for n in got if n == value]
            if same:
                bad.append(
                    f"encoding_variants({value!r}) -> {got}, "
                    f"every neighbor must differ from the input but {same} did not"
                )
    return bad


def run():
    bad = probe_encoding_variants()
    for line in bad:
        print(line)
    print(f"probe_encoding_variants: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
