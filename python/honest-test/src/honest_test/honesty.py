"""The honesty, chain-contract, auth and gate checks (spec section 4).

Each check takes the live callables and declarations as data and returns a list of Finding
records — one per violation, empty when the property holds. The links, chains, monitors,
providers and run_transition functions are injected, so a check runs real code and performs no
I/O of its own.
"""

import copy

from honest_type import is_fault
from honest_type.chains import link_meta

from honest_test._util import _pick, _read_or
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


def _purity_check(link, test_manifest):
    """The non-boundary arm of verify_purity (spec section 4.1): non_deterministic when two runs on
    one manifest differ."""
    return _pick(
        link(test_manifest) != link(test_manifest),
        lambda: [_finding("failure", "non_deterministic",
                          "link produced different results on identical input")],
        lambda: [],
    )


def verify_purity(link, test_manifest):
    """Run a link twice on the same manifest and report non_deterministic when results differ
    (spec section 4.1). A declared boundary is exempt. Performs no I/O of its own."""
    return _pick(_is_boundary(link), lambda: [], lambda: _purity_check(link, test_manifest))


def detect_mutation(link, test_manifest):
    """Deep-copy the manifest, run the link, and report manifest_mutated when the input changed
    (spec section 4.2). Performs no I/O of its own."""
    before = copy.deepcopy(test_manifest)
    link(test_manifest)
    return _pick(
        test_manifest != before,
        lambda: [_finding("failure", "manifest_mutated",
                          f"link modified its input manifest: before={before!r} after={test_manifest!r}")],
        lambda: [],
    )


def _idempotency_check(chain, test_manifest):
    """The non-boundary arm of test_idempotency (spec section 4.3): not_idempotent when two runs on
    identical input differ."""
    return _pick(
        chain(test_manifest) != chain(copy.deepcopy(test_manifest)),
        lambda: [_finding("failure", "not_idempotent",
                          "chain produced different results on identical input")],
        lambda: [],
    )


def test_idempotency(chain, test_manifest):
    """Run a chain twice, the second time on a deep copy, and report not_idempotent when the two
    results differ (spec section 4.3). A chain with a boundary link is exempt. No I/O of its own."""
    return _pick(_is_boundary(chain), lambda: [], lambda: _idempotency_check(chain, test_manifest))


# The two monitored honesty checks (spec sections 4.4, 4.5) share one body and differ only in the
# warning they raise. The check kind names which: io for boundary isolation (the io_monitor records
# I/O), nondeterminism for determinism (the call_monitor records a non-deterministic source).
_MONITORED_CHECKS = {
    "io": ("io_detected", "link performed I/O; add boundary=True if intentional"),
    "nondeterminism": ("nondeterminism_detected", "link called a non-deterministic source; it belongs at a boundary"),
}


def _raise_unknown_kind(kind):
    """The no-match row of _MONITORED_CHECKS (spec sections 4.4, 4.5): an unknown kind is a program
    bug, so it halts rather than resolving to a wrong check."""
    accepted = sorted(_MONITORED_CHECKS)
    raise KeyError(f"monitor kind {kind!r} matched no check; accepted kinds are {accepted}")


def _monitor_result(link, test_manifest, monitor, row):
    """Run the link under the monitor and warn when the watched effect happened (spec sections 4.4,
    4.5)."""
    code, message = row
    return _pick(
        monitor(link, test_manifest),
        lambda: [_finding("warning", code, message)],
        lambda: [],
    )


def _monitored(link, test_manifest, monitor, kind):
    """The non-boundary arm of verify_under_monitor (spec sections 4.4, 4.5): resolve the kind to
    its warning, halting on an unknown kind."""
    row = _read_or(_MONITORED_CHECKS, kind, None)
    return _pick(
        row is None,
        lambda: _raise_unknown_kind(kind),
        lambda: _monitor_result(link, test_manifest, monitor, row),
    )


def verify_under_monitor(link, test_manifest, monitor, kind):
    """Run a link under the injected monitor and warn for a non-boundary link the monitor caught
    (spec sections 4.4, 4.5). The monitor runs the link and returns the record of detected calls; a
    non-empty record means the watched effect happened. kind picks the warning from
    _MONITORED_CHECKS — io for boundary isolation, nondeterminism for determinism — so one check is
    parameterized by the kind rather than written once per monitor. The warning reports, never
    blocks."""
    return _pick(_is_boundary(link), lambda: [], lambda: _monitored(link, test_manifest, monitor, kind))


def _check_downstream(downstream, upstream_result, findings):
    """Run the downstream link on a valid upstream output and report chain_contract on a server
    fault (spec section 4.6)."""
    downstream_result = downstream(upstream_result)
    broken = is_fault(downstream_result) and _read_or(downstream_result, "category", None) == "server"
    _pick(
        broken,
        lambda: findings.append(_finding(
            "failure", "chain_contract",
            "downstream link rejected a valid upstream output with a server fault")),
        lambda: None,
    )


def _check_join(upstream, downstream, manifest, findings):
    """Check one adjacent-link join for one manifest (spec section 4.6): a faulting upstream output
    is not a join to check, so it is skipped."""
    upstream_result = upstream(manifest)
    _pick(
        is_fault(upstream_result),
        lambda: None,
        lambda: _check_downstream(downstream, upstream_result, findings),
    )


def test_chain_contracts(links, vocab, binding):
    """Check each adjacent pair of links and report chain_contract on a broken join (spec section
    4.6): every valid output of one link must be accepted by the next. Only a server fault from
    the downstream link is a broken join; a client fault is not. No I/O of its own."""
    findings = []
    cases = enumerate_test_cases(vocab, binding)
    for index in range(len(links) - 1):
        upstream, downstream = links[index], links[index + 1]
        for manifest in cases:
            _check_join(upstream, downstream, manifest, findings)
    return findings


def _raise_unknown_token(token_class):
    """The no-match row of _TOKEN_STATUS (spec section 4.7): an unknown token class is a program
    bug, so it halts rather than resolving to a wrong status."""
    accepted = sorted(_TOKEN_STATUS)
    raise KeyError(f"token class {token_class!r} matched no status; accepted classes are {accepted}")


def _default_status(token_class):
    """The framework-default HTTP status for a token class (spec section 4.7), halting on an unknown
    class."""
    row = _read_or(_TOKEN_STATUS, token_class, None)
    return _pick(row is None, lambda: _raise_unknown_token(token_class), lambda: row)


def compute_expected_status(token_class, fault_mapping):
    """Map one token class to the HTTP status the auth-honesty check expects (spec section 4.7).
    The provider's fault_mapping overrides the default per class. Reads no world, pure data."""
    return _pick(
        token_class in fault_mapping,
        lambda: fault_mapping[token_class],
        lambda: _default_status(token_class),
    )


def _fault_status(provider, auth_fault):
    """The HTTP status a resolve_actor fault maps to (honest-auth section 2.5): the provider's
    fault_mapping for the fault's category, else the framework default, else 500."""
    category = auth_fault["category"]
    return _pick(
        category in provider["fault_mapping"],
        lambda: provider["fault_mapping"][category],
        lambda: _read_or(_CATEGORY_STATUS, category, 500),
    )


def _probe_malformed(provider, token_class, token):
    """A malformed token must be rejected at the recognizer (spec section 4.7)."""
    return _pick(
        provider["actor_recognizer"](token),
        lambda: [_finding("failure", "auth_honesty",
                          "provider accepted a malformed token at the recognizer")],
        lambda: [],
    )


def _probe_valid(provider, token_class, token):
    """A valid token must resolve to a bare actor, not a fault (spec section 4.7)."""
    result = provider["resolve_actor"](token)
    return _pick(
        is_fault(result),
        lambda: [_finding("failure", "auth_honesty", "provider rejected a valid token")],
        lambda: [],
    )


def _probe_other(provider, token_class, token):
    """Every non-valid, non-malformed token class must fault with the expected HTTP status (spec
    section 4.7)."""
    result = provider["resolve_actor"](token)
    expected = compute_expected_status(token_class, provider["fault_mapping"])
    wrong = not is_fault(result) or _fault_status(provider, result) != expected
    return _pick(
        wrong,
        lambda: [_finding("failure", "auth_honesty",
                          f"provider did not fault correctly for token class {token_class!r}")],
        lambda: [],
    )


_TOKEN_PROBES = {"malformed": _probe_malformed, "valid": _probe_valid}


def _probe_token(provider, token_class, token):
    """Probe one token class (spec section 4.7): malformed and valid have their own checks, every
    other class takes the fault-and-status check."""
    probe = _read_or(_TOKEN_PROBES, token_class, _probe_other)
    return probe(provider, token_class, token)


def test_auth_honesty(provider):
    """Probe each of the six token classes and report auth_honesty on wrong behaviour (spec
    section 4.7): a malformed token must be rejected at the recognizer, a valid token must
    resolve to a bare actor (a non-fault by is_fault), every other class must fault with the
    expected HTTP status. resolve_actor returns a bare actor or a bare Fault, no ok/err envelope
    (honest-type 12.1). No I/O of its own; the provider's resolve_actor is the injected boundary."""
    findings = []
    for token_class in _TOKEN_CLASSES:
        token = provider["test_token_generator"](token_class, {})
        findings.extend(_probe_token(provider, token_class, token))
    return findings


def _proof_findings(gate, proof):
    """The arm of check_gate_honesty for a gate that names a proof (spec section 4.9):
    gate_proof_unbound when the proof does not bind the failure it expects."""
    return _pick(
        not proof.get("binds_failure"),
        lambda: [_finding(
            "rejection", "gate_proof_unbound",
            f"the proof for {gate.get('name')!r} does not bind the failure it expects",
            _read_or(proof, "location", ""))],
        lambda: [],
    )


def _gate_findings(gate):
    """The findings for one gate (spec section 4.9): gate_unverified when it names no proof, else
    the proof is checked for a bound failure."""
    proof = gate.get("proof")
    return _pick(
        proof is None,
        lambda: [_finding(
            "rejection", "gate_unverified",
            f"gate {gate.get('name')!r} has no proof-of-failure",
            _read_or(gate, "location", ""))],
        lambda: _proof_findings(gate, proof),
    )


def check_gate_honesty(gates):
    """Require every declared gate to name a bound proof-of-failure test (spec section 4.9):
    gate_unverified for a gate with no proof, gate_proof_unbound for a proof that does not bind
    the specific failure. One rejection per dishonest gate, empty when every gate is proven.
    Reads no world, returns pure data."""
    findings = []
    for gate in gates:
        findings.extend(_gate_findings(gate))
    return findings
