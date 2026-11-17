"""RED probe for honest-test.enumerate_sets — the Set-based case generator (.hd, spec section 3.2).

enumerate_sets enumerates every member of every Set recognizer in a vocabulary and
produces the Cartesian product of their members, no sampling. Each case is a manifest:
a map from each Set slot's name (the type name) to the member chosen for it. A
predicate recognizer contributes no slot, so a vocabulary of only predicates
enumerates to one empty manifest. It reads no world and returns pure data.
honest-test has no code yet, so importing honest_test fails — the correct red state.
"""

from honest_type import predicate, vocabulary

from honest_test import enumerate_sets


def _manifest_set(manifests):
    """The list of manifest dicts as an order-independent set of frozensets of items,
    so the Cartesian product is compared without asserting enumeration order."""
    return {frozenset(m.items()) for m in manifests}


def _build(decls):
    vocab = vocabulary(decls)
    if isinstance(vocab, dict) and "code" in vocab:
        return None, f"vocabulary({decls!r}) faulted: {vocab!r}"
    return vocab, None


def probe_enumerate_sets():
    """enumerate_sets yields one manifest per member for one Set, the full product for
    two Sets, one empty manifest for a predicate-only vocabulary, and ignores predicate
    recognizers that sit alongside a Set."""
    bad = []

    # One Set of two members -> two single-slot manifests keyed by the type name.
    one, err = _build({"color": {"crimson", "azure"}})
    if err:
        bad.append(err)
    else:
        got = _manifest_set(enumerate_sets(one))
        want = {frozenset({("color", "crimson")}), frozenset({("color", "azure")})}
        if got != want:
            bad.append(f"one Set of 2 -> {got!r}, expected {want!r}")

    # Two Sets -> the full Cartesian product, 2 x 2 = 4 manifests of two slots each.
    two, err = _build({"color": {"crimson", "azure"}, "size": {"small", "large"}})
    if err:
        bad.append(err)
    else:
        got = _manifest_set(enumerate_sets(two))
        want = {
            frozenset({("color", "crimson"), ("size", "small")}),
            frozenset({("color", "crimson"), ("size", "large")}),
            frozenset({("color", "azure"), ("size", "small")}),
            frozenset({("color", "azure"), ("size", "large")}),
        }
        if got != want:
            bad.append(f"two Sets of 2x2 -> {got!r}, expected the 4-case product {want!r}")
        if len(list(enumerate_sets(two))) != 4:
            bad.append("two Sets of 2x2 must yield exactly 4 cases, no sampling and no duplication")

    # A vocabulary of only predicate recognizers enumerates to one empty manifest.
    pred_only, err = _build({"tag": predicate(lambda s: s == "vip")})
    if err:
        bad.append(err)
    else:
        got = list(enumerate_sets(pred_only))
        if got != [{}]:
            bad.append(f"a predicate-only vocabulary must enumerate to [{{}}], got {got!r}")

    # A predicate alongside a Set contributes no slot: only the Set's members appear.
    mixed, err = _build({"color": {"crimson", "azure"}, "tag": predicate(lambda s: s == "vip")})
    if err:
        bad.append(err)
    else:
        got = _manifest_set(enumerate_sets(mixed))
        want = {frozenset({("color", "crimson")}), frozenset({("color", "azure")})}
        if got != want:
            bad.append(f"a Set plus a predicate -> {got!r}, expected only the Set's 2 cases {want!r}")

    return bad


def run():
    failures = probe_enumerate_sets()
    for message in failures:
        print(f"FAIL enumerate_sets: {message}")
    print(f"enumerate_sets probe: {'PASS' if not failures else str(len(failures)) + ' failed'}")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)
