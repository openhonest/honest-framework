"""honest-test conformance: encoding_variants — the encoding-variant neighbor class.

The spec lists six variants (§3.5, class 5). Three are fixed exactly and three depend on
the reference implementation's byte-level helpers (overlong UTF-8, double percent-encoding,
mixed UTF-8/latin-1), which the spec does not pin. This probe asserts the three the spec
fixes — a UTF-16 byte-order-mark prefix, a space replaced by a non-breaking space, and a
space replaced by a LINE SEPARATOR — and that at least the six variants are produced.

No classes, no mocks. It calls the real honest_test.encoding_variants and reads membership.
"""

from honest_test import encoding_variants


def probe_encoding_variants():
    bad = []
    value = "a b"  # a space makes the whitespace-normalization variants meaningful
    got = encoding_variants(value)
    if not isinstance(got, list):
        return [f"encoding_variants({value!r}) -> {type(got).__name__}, expected a list"]
    got_set = set(got)
    pinned = {
        "﻿" + value: "a UTF-16 byte-order-mark prefix",
        value.replace(" ", "\xa0"): "a non-breaking space for the space",
        value.replace(" ", " "): "a LINE SEPARATOR for the space",
    }
    for want, label in pinned.items():
        if want not in got_set:
            bad.append(f"encoding_variants({value!r}) should include {label}: {want!r}")
    if len(got) < 6:
        bad.append(f"encoding_variants({value!r}) returned {len(got)} variants, the spec lists six")
    return bad


def run():
    messages = probe_encoding_variants()
    if messages:
        print(f"FAIL HTEST-probe [encoding_variants]: {messages}")
    print(f"encoding_variants: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 1 if messages else 0


if __name__ == "__main__":
    raise SystemExit(run())
