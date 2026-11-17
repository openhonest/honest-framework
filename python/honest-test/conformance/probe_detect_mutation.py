"""honest-test conformance: detect_mutation flags a link that modified its input manifest.

Spec section 4.2, feature "detect_mutation flags a link that modified its input
manifest", .hd detect_mutation. A pure function must not modify its input:
detect_mutation deep-copies the manifest, runs the injected link, and returns a
manifest_mutated failure when the manifest after the run differs from the copy, the empty
list when the input was untouched.

No classes, no mocks. One real link reads its manifest and returns a fresh value without
touching the input; one real link writes into the manifest in place. Each is handed a
fresh manifest so the two runs do not interfere. A Finding carries a "code" and a "kind".
"""

from honest_test import detect_mutation


def _codes(findings):
    return [f.get("code") for f in findings if isinstance(f, dict)]


def _non_mutating_link(manifest):
    """Reads the manifest, returns a fresh dict, leaves the input untouched."""
    return {"ok": dict(manifest)}


def _mutating_link(manifest):
    """Writes a new key into its input manifest in place — the mutation case."""
    manifest["injected"] = True
    return {"ok": manifest}


def probe_detect_mutation():
    bad = []

    clean = detect_mutation(_non_mutating_link, {"slot": "value"})
    if clean != []:
        bad.append(f"a link that leaves its input untouched should yield no finding, got {clean!r}")

    dirty = detect_mutation(_mutating_link, {"slot": "value"})
    if _codes(dirty) != ["manifest_mutated"]:
        bad.append(
            f"a link that modifies its input manifest should yield one manifest_mutated "
            f"failure, got {dirty!r}"
        )
    elif dirty[0].get("kind") != "failure":
        bad.append(f"the manifest_mutated finding must be graded a failure, got kind {dirty[0].get('kind')!r}")

    return bad


def run():
    messages = probe_detect_mutation()
    for message in messages:
        print(f"FAIL HT-probe [detect_mutation]: {message}")
    print(f"detect_mutation: {'passed' if not messages else f'{len(messages)} failed'}")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
