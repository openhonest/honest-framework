"""honest-test conformance: unicode_confusables — the Unicode-confusable neighbor class.

The spec documents the confusable map as a curated subset of Unicode Technical Standard 39
(§3.5, class 2), larger than it prints, so this probe pins only what the spec fixes by name.
For 'a' the spec documents four confusables: Cyrillic а (U+0430), IPA ɑ (U+0251), fullwidth
ａ (U+FF41) and mathematical 𝐚 (U+1D41A). The probe asserts each of those four appears as a
one-position substitution of 'a', that the full-homoglyph neighbor (the first confusable,
Cyrillic а) appears, and that the value is never returned unchanged.

No classes, no mocks. It calls the real honest_test.unicode_confusables and reads membership.
"""

from honest_test import unicode_confusables

# The four confusables §3.5 documents inline for 'a'. The first is the one the full-homoglyph
# pass substitutes, so it must appear both per-position and as the whole-value neighbor.
_DOCUMENTED_A = ["а", "ɑ", "ａ", "\U0001d41a"]


def probe_unicode_confusables():
    bad = []
    got = unicode_confusables("a")
    if not isinstance(got, list):
        return [f"unicode_confusables('a') -> {type(got).__name__}, expected a list"]
    got_set = set(got)
    for conf in _DOCUMENTED_A:
        if conf not in got_set:
            bad.append(f"unicode_confusables('a') should substitute 'a' with U+{ord(conf):04X}")
    if "а" not in got_set:
        bad.append("unicode_confusables('a') should include the full-homoglyph neighbor (Cyrillic а)")
    if "a" in got_set:
        bad.append("unicode_confusables('a') must not return the value unchanged")
    return bad


def run():
    messages = probe_unicode_confusables()
    if messages:
        print(f"FAIL HTEST-probe [unicode_confusables]: {messages}")
    print(f"unicode_confusables: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 1 if messages else 0


if __name__ == "__main__":
    raise SystemExit(run())
