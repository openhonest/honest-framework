"""honest-test conformance: adversarial_neighbors — the deduplicated union of five classes.

The spec fixes the composition (§3.5): adversarial_neighbors returns the deduplicated union
of the edit-distance-1, Unicode-confusable, control-character, length-extension and
encoding-variant classes, with the original value removed. This probe builds the known-good
union from the real five class functions and asserts adversarial_neighbors equals it as a
set, carries no duplicates, and never contains the original value.

No classes, no mocks. It calls the real honest_test functions and compares the union.
"""

from honest_test import (
    adversarial_neighbors,
    control_characters,
    edit_distance_1,
    encoding_variants,
    length_extensions,
    unicode_confusables,
)


def probe_adversarial_neighbors():
    bad = []
    value = "Ab"
    expected = set(
        edit_distance_1(value)
        + unicode_confusables(value)
        + control_characters(value)
        + length_extensions(value)
        + encoding_variants(value)
    )
    expected.discard(value)

    got = adversarial_neighbors(value)
    if not isinstance(got, list):
        return [f"adversarial_neighbors({value!r}) -> {type(got).__name__}, expected a list"]
    got_set = set(got)

    if value in got_set:
        bad.append("adversarial_neighbors must remove the original value from the union")
    if len(got) != len(got_set):
        bad.append("adversarial_neighbors must deduplicate: the returned list carries duplicates")
    if got_set != expected:
        missing = expected - got_set
        extra = got_set - expected
        if missing:
            bad.append(f"adversarial_neighbors is missing {len(missing)} neighbor(s) the five classes produce")
        if extra:
            bad.append(f"adversarial_neighbors produced {len(extra)} neighbor(s) no class produces")
    return bad


def run():
    messages = probe_adversarial_neighbors()
    if messages:
        print(f"FAIL HTEST-probe [adversarial_neighbors]: {messages}")
    print(f"adversarial_neighbors: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 1 if messages else 0


if __name__ == "__main__":
    raise SystemExit(run())
