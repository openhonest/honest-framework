"""The honesty, chain-contract, auth and gate checks (spec section 4).

Each check takes the live callables and declarations as data and returns a list of Finding
records — one per violation, empty when the property holds. The links, chains, monitors,
providers and run_transition functions are injected, so a check runs real code and performs no
I/O of its own.
"""

import copy

from honest_type.chains import link_meta

from honest_test.generators import enumerate_test_cases
from honest_test.support import _finding

# Framework default fault-category -> HTTP status (honest-auth section 2.5), carried here because
# honest-test does not depend on honest-auth. A provider's fault_mapping overrides per category.
_CATEGORY_STATUS = {"unauthenticated": 401, "forbidden": 403, "conflict": 409, "client": 400, "server": 500}

# The default token-class -> expected HTTP status (spec section 4.7). valid takes the success path
# (200); the four unauthenticated classes are 401; malformed is rejected at the recognizer (400).
_TOKEN_STATUS = {"valid": 200, "revoked": 401, "expired": 401, "missing": 401, "forged": 401, "malformed": 400}

_TOKEN_CLASSES = ("valid", "revoked", "expired", "malformed", "missing", "forged")


def _is_boundary(link):
    """Whether a link is declared a boundary (honest-type link_meta); a plain function is not."""
    return bool(link_meta(link).get("boundary"))


def verify_purity(link, test_manifest):
    """Run a link twice on the same manifest and report non_deterministic when results differ
    (spec section 4.1). A declared boundary is exempt. Performs no I/O of its own."""
    if _is_boundary(link):
        return []
    if link(test_manifest) != link(test_manifest):
        return [_finding("failure", "non_deterministic",
                         "link produced different results on identical input")]
    return []


def detect_mutation(link, test_manifest):
    """Deep-copy the manifest, run the link, and report manifest_mutated when the input changed
    (spec section 4.2). Performs no I/O of its own."""
    before = copy.deepcopy(test_manifest)
    link(test_manifest)
    if test_manifest != before:
        return [_finding("failure", "manifest_mutated",
                         f"link modified its input manifest: before={before!r} after={test_manifest!r}")]
    return []


def test_idempotency(chain, test_manifest):
    """Run a chain twice, the second time on a deep copy, and report not_idempotent when the two
    results differ (spec section 4.3). A chain with a boundary link is exempt. No I/O of its own."""
    if _is_boundary(chain):
        return []
    if chain(test_manifest) != chain(copy.deepcopy(test_manifest)):
        return [_finding("failure", "not_idempotent",
                         "chain produced different results on identical input")]
    return []


# The two monitored honesty checks (spec sections 4.4, 4.5) share one body and differ only in the
# warning they raise. The check kind names which: io for boundary isolation (the io_monitor records
# I/O), nondeterminism for determinism (the call_monitor records a non-deterministic source).
_MONITORED_CHECKS = {
    "io": ("io_detected", "link performed I/O; add boundary=True if intentional"),
    "nondeterminism": ("nondeterminism_detected", "link called a non-deterministic source; it belongs at a boundary"),
}


def verify_under_monitor(link, test_manifest, monitor, kind):
    """Run a link under the injected monitor and warn for a non-boundary link the monitor caught
    (spec sections 4.4, 4.5). The monitor runs the link and returns the record of detected calls; a
    non-empty record means the watched effect happened. kind picks the warning from
    _MONITORED_CHECKS — io for boundary isolation, nondeterminism for determinism — so one check is
    parameterized by the kind rather than written once per monitor. The warning reports, never
    blocks."""
    if _is_boundary(link):
        return []
    code, message = _MONITORED_CHECKS[kind]
    if monitor(link, test_manifest):
        return [_finding("warning", code, message)]
    return []


def test_chain_contracts(links, vocab, binding):
    """Check each adjacent pair of links and report chain_contract on a broken join (spec section
    4.6): every valid output of one link must be accepted by the next. Only a server fault from
    the downstream link is a broken join; a client fault is not. No I/O of its own."""
    findings = []
    cases = enumerate_test_cases(vocab, binding)
    for index in range(len(links) - 1):
        upstream, downstream = links[index], links[index + 1]
        for manifest in cases:
            upstream_result = upstream(manifest)
            if "ok" not in upstream_result:
                continue
            downstream_result = downstream(upstream_result["ok"])
            if "err" in downstream_result and downstream_result["err"].get("category") == "server":
                findings.append(_finding(
                    "failure", "chain_contract",
                    "downstream link rejected a valid upstream output with a server fault"))
    return findings


def compute_expected_status(token_class, fault_mapping):
    """Map one token class to the HTTP status the auth-honesty check expects (spec section 4.7).
    The provider's fault_mapping overrides the default per class. Reads no world, pure data."""
    if token_class in fault_mapping:
        return fault_mapping[token_class]
    return _TOKEN_STATUS[token_class]


def _fault_status(provider, auth_fault):
    """The HTTP status a resolve_actor fault maps to (honest-auth section 2.5): the provider's
    fault_mapping for the fault's category, else the framework default, else 500."""
    category = auth_fault["category"]
    return provider["fault_mapping"].get(category, _CATEGORY_STATUS.get(category, 500))


def test_auth_honesty(provider):
    """Probe each of the six token classes and report auth_honesty on wrong behaviour (spec
    section 4.7): a malformed token must be rejected at the recognizer, a valid token must
    resolve to ok(actor), every other class must fault with the expected HTTP status. No I/O of
    its own; the provider's resolve_actor is the injected boundary."""
    findings = []
    for token_class in _TOKEN_CLASSES:
        token = provider["test_token_generator"](token_class, {})
        if token_class == "malformed":
            if provider["actor_recognizer"](token):
                findings.append(_finding("failure", "auth_honesty",
                                         "provider accepted a malformed token at the recognizer"))
            continue
        result = provider["resolve_actor"](token)
        if token_class == "valid":
            if "ok" not in result:
                findings.append(_finding("failure", "auth_honesty",
                                         "provider rejected a valid token"))
            continue
        expected = compute_expected_status(token_class, provider["fault_mapping"])
        if "err" not in result or _fault_status(provider, result["err"]) != expected:
            findings.append(_finding("failure", "auth_honesty",
                                     f"provider did not fault correctly for token class {token_class!r}"))
    return findings


def check_gate_honesty(gates):
    """Require every declared gate to name a bound proof-of-failure test (spec section 4.9):
    gate_unverified for a gate with no proof, gate_proof_unbound for a proof that does not bind
    the specific failure. One rejection per dishonest gate, empty when every gate is proven.
    Reads no world, returns pure data."""
    findings = []
    for gate in gates:
        proof = gate.get("proof")
        if proof is None:
            findings.append(_finding(
                "rejection", "gate_unverified",
                f"gate {gate.get('name')!r} has no proof-of-failure", gate.get("location", "")))
        elif not proof.get("binds_failure"):
            findings.append(_finding(
                "rejection", "gate_proof_unbound",
                f"the proof for {gate.get('name')!r} does not bind the failure it expects",
                proof.get("location", "")))
    return findings
