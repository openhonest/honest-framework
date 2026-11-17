"""honest-test conformance: test_chain_contracts checks each adjacent link join.

Spec section 4.6, feature "test_chain_contracts checks each adjacent link join", .hd
test_chain_contracts. For each adjacent pair it enumerates the input cases the upstream
link accepts, runs the upstream link, and when that produces a manifest feeds it to the
downstream link, returning a chain_contract failure when the downstream link rejects that
valid output with a server fault. A client fault from the downstream link is not a
contract failure — only a server fault indicates a broken join.

No classes, no mocks. The links are real pure functions defined here and injected as a
list. The vocabulary and binding are genuine honest-type values that drive the case
enumeration. A link returns the bare-union shape every real link returns since the
bare-union migration: a bare manifest, or a bare Fault carrying a "code" and a "category"
("server" or "client"), recognized by is_fault — never wrapped in an ok/err envelope. A
Finding carries a "code" and a "kind".
"""

from honest_type import binding, fault, is_fault, vocabulary

from honest_test import test_chain_contracts

_VOCAB = vocabulary({"color": {"alpha", "beta", "gamma"}})
_BINDING = binding({"color": "color"})


def _codes(findings):
    return [f.get("code") for f in findings if isinstance(f, dict)]


def _upstream(manifest):
    """Produces a bare manifest the downstream link must accept — no ok() wrapper."""
    return {"token": "x"}


def _downstream_good(manifest):
    """Accepts the upstream's valid output and returns a bare manifest — the join holds."""
    return manifest


def _downstream_server_fault(manifest):
    """Rejects the upstream's valid output with a bare server fault — the broken join."""
    return fault("rejected", "downstream refused a valid upstream output", "server", [], {})


def _downstream_client_fault(manifest):
    """Rejects with a bare client fault — not a contract failure."""
    return fault("bad_input", "downstream reports a client error", "client", [], {})


def _upstream_fault(manifest):
    """Rejects its own input with a bare fault: there is no valid output to check downstream."""
    return fault("upstream_reject", "upstream refused the input", "client", [], {})


def probe_test_chain_contracts():
    bad = []

    if is_fault(_VOCAB):
        return [f"the test vocabulary did not build: {_VOCAB!r}"]

    holds = test_chain_contracts([_upstream, _downstream_good], _VOCAB, _BINDING)
    if holds != []:
        bad.append(f"a chain whose every join holds should yield no finding, got {holds!r}")

    broken = test_chain_contracts([_upstream, _downstream_server_fault], _VOCAB, _BINDING)
    if not broken or set(_codes(broken)) != {"chain_contract"}:
        bad.append(
            f"a downstream link rejecting a valid upstream output with a server fault "
            f"should yield chain_contract failures, got {broken!r}"
        )
    elif {f.get("kind") for f in broken} != {"failure"}:
        bad.append(f"a chain_contract finding must be graded a failure, got {broken!r}")

    client = test_chain_contracts([_upstream, _downstream_client_fault], _VOCAB, _BINDING)
    if client != []:
        bad.append(f"a client fault from the downstream link is not a contract failure, got {client!r}")

    up_faults = test_chain_contracts([_upstream_fault, _downstream_server_fault], _VOCAB, _BINDING)
    if up_faults != []:
        bad.append(
            "when the upstream link faults there is no valid output to check downstream, "
            f"so no finding, got {up_faults!r}"
        )

    return bad


def run():
    messages = probe_test_chain_contracts()
    for message in messages:
        print(f"FAIL HT-probe [test_chain_contracts]: {message}")
    print(f"test_chain_contracts: {'passed' if not messages else f'{len(messages)} failed'}")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
