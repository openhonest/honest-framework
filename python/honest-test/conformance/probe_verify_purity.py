"""honest-test conformance: verify_purity runs a link twice and flags a different result.

Spec section 4.1, feature "verify_purity runs a link twice and flags a different
result", .hd verify_purity. A pure function must return the same output for the same
input, always: verify_purity runs the injected link twice on one manifest and returns a
non_deterministic failure when the two results differ, the empty list when they match.

No classes, no mocks. The link handed in is a real pure function defined here, used as
test input, not a stand-in: one genuinely pure link whose output depends only on its
manifest, and one deliberately impure link that returns a different result each call. A
Finding is recognized by its own shape — it carries a "code" and a "kind".
"""

from honest_test import verify_purity


def _codes(findings):
    return [f.get("code") for f in findings if isinstance(f, dict)]


def _pure_link(manifest):
    """Deterministic: the output depends only on the manifest, so two runs match."""
    return {"ok": {"size": len(manifest)}}


def _make_impure_link():
    """A link that returns a different result on each call — the non-deterministic case."""
    state = {"n": 0}

    def link(manifest):
        state["n"] += 1
        return {"ok": {"n": state["n"]}}

    return link


def probe_verify_purity():
    bad = []

    clean = verify_purity(_pure_link, {"slot": "value"})
    if clean != []:
        bad.append(f"a pure link run twice on one manifest should yield no finding, got {clean!r}")

    dirty = verify_purity(_make_impure_link(), {"slot": "value"})
    if _codes(dirty) != ["non_deterministic"]:
        bad.append(
            f"a link returning a different result on identical input should yield one "
            f"non_deterministic failure, got {dirty!r}"
        )
    elif dirty[0].get("kind") != "failure":
        bad.append(f"the non_deterministic finding must be graded a failure, got kind {dirty[0].get('kind')!r}")

    return bad


def run():
    messages = probe_verify_purity()
    for message in messages:
        print(f"FAIL HT-probe [verify_purity]: {message}")
    print(f"verify_purity: {'passed' if not messages else f'{len(messages)} failed'}")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
