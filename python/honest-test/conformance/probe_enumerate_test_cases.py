"""RED probe for honest-test.enumerate_test_cases — the link-input case builder (.hd, spec sections 3.2, 4.6).

enumerate_test_cases enumerates the vocabulary a link accepts the way enumerate_sets
does, then resolves each combination into a manifest through the binding, so the slot
each member fills is the binding slot name, not the type name. The same Maybe and
predicate rules hold: a Maybe slot adds its absent arm, binding that slot to Nothing
(a null value). It reads no world and returns pure data.
honest-test has no code yet, so importing honest_test fails — the correct red state.
"""

from honest_type import binding, maybe, vocabulary

from honest_test import enumerate_test_cases


def _manifest_set(manifests):
    """The list of manifest dicts as an order-independent set of frozensets of items."""
    return {frozenset(m.items()) for m in manifests}


def _vocab(decls):
    vocab = vocabulary(decls)
    if isinstance(vocab, dict) and "code" in vocab:
        return None, f"vocabulary({decls!r}) faulted: {vocab!r}"
    return vocab, None


def probe_enumerate_test_cases():
    """enumerate_test_cases names each slot from the binding, builds the product across
    two Sets, and adds the Nothing arm for a Maybe slot."""
    bad = []

    # The binding renames the type 'color' to the slot 'shade'.
    one, err = _vocab({"color": {"crimson", "azure"}})
    if err:
        bad.append(err)
    else:
        got = _manifest_set(enumerate_test_cases(one, binding({"color": "shade"})))
        want = {frozenset({("shade", "crimson")}), frozenset({("shade", "azure")})}
        if got != want:
            bad.append(f"one Set bound to 'shade' -> {got!r}, expected {want!r}")

    # Two Sets, each renamed by the binding -> the 2x2 product on the slot names.
    two, err = _vocab({"color": {"crimson", "azure"}, "size": {"small", "large"}})
    if err:
        bad.append(err)
    else:
        got = _manifest_set(enumerate_test_cases(two, binding({"color": "c", "size": "sz"})))
        want = {
            frozenset({("c", "crimson"), ("sz", "small")}),
            frozenset({("c", "crimson"), ("sz", "large")}),
            frozenset({("c", "azure"), ("sz", "small")}),
            frozenset({("c", "azure"), ("sz", "large")}),
        }
        if got != want:
            bad.append(f"two Sets bound to 'c'/'sz' -> {got!r}, expected the 4-case product {want!r}")

    # A Maybe slot adds its absent arm: besides one case per member, one binding the
    # slot to Nothing (a null value). A Maybe Set of 2 members -> 3 cases.
    mb, err = _vocab({"color": {"crimson", "azure"}})
    if err:
        bad.append(err)
    else:
        got = _manifest_set(enumerate_test_cases(mb, binding({"color": maybe("shade")})))
        want = {
            frozenset({("shade", "crimson")}),
            frozenset({("shade", "azure")}),
            frozenset({("shade", None)}),
        }
        if got != want:
            bad.append(f"a Maybe Set of 2 -> {got!r}, expected 3 cases incl. the Nothing arm {want!r}")

    return bad


def run():
    failures = probe_enumerate_test_cases()
    for message in failures:
        print(f"FAIL enumerate_test_cases: {message}")
    print(f"enumerate_test_cases probe: {'PASS' if not failures else str(len(failures)) + ' failed'}")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)
