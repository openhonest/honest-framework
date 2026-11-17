"""honest-test conformance: test_idempotency flags a chain that is not idempotent.

Spec section 4.3, feature "test_idempotency flags a chain that is not idempotent", .hd
test_idempotency. The same chain run twice on the same manifest must produce the same
result: test_idempotency runs the injected chain twice, the second time on a deep copy of
the manifest, and returns a not_idempotent failure when the two results differ, the empty
list when the chain is idempotent.

No classes, no mocks. One real chain's output depends only on its manifest; one real
chain carries a counter and returns a different result each call. A Finding carries a
"code" and a "kind".
"""

from honest_test import test_idempotency


def _codes(findings):
    return [f.get("code") for f in findings if isinstance(f, dict)]


def _idempotent_chain(manifest):
    """Deterministic: two runs on equal manifests return equal results."""
    return {"ok": {"size": len(manifest)}}


def _make_non_idempotent_chain():
    """A chain that returns a different result on each call — the not-idempotent case."""
    state = {"n": 0}

    def chain(manifest):
        state["n"] += 1
        return {"ok": {"n": state["n"]}}

    return chain


def probe_test_idempotency():
    bad = []

    clean = test_idempotency(_idempotent_chain, {"slot": "value"})
    if clean != []:
        bad.append(f"an idempotent chain run twice should yield no finding, got {clean!r}")

    dirty = test_idempotency(_make_non_idempotent_chain(), {"slot": "value"})
    if _codes(dirty) != ["not_idempotent"]:
        bad.append(
            f"a chain returning a different result on identical input should yield one "
            f"not_idempotent failure, got {dirty!r}"
        )
    elif dirty[0].get("kind") != "failure":
        bad.append(f"the not_idempotent finding must be graded a failure, got kind {dirty[0].get('kind')!r}")

    return bad


def run():
    messages = probe_test_idempotency()
    for message in messages:
        print(f"FAIL HT-probe [test_idempotency]: {message}")
    print(f"test_idempotency: {'passed' if not messages else f'{len(messages)} failed'}")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
