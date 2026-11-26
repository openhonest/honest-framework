"""The honesty, chain-contract, auth, gate and test-body checks (spec sections 4.1
through 4.9). Callback readers invoke supplied functions. Finding functions turn
observed values into records with a kind, code, message and location.
"""

import copy

from honest_parse import line_col, walk
from honest_type import is_fault, link_meta

from honest_test._util import _choose, _pick, _read_or
from honest_test.generate import enumerate_test_cases

_finding = lambda kind, code, message, location: {"kind": kind, "code": code, "message": message, "location": location}
_is_ok = lambda result: hasattr(result, "get") and "ok" in result
_err_fault = lambda result: _read_or(result, "err", None)

_REBIND_METHODS = {"setattr", "setitem", "delattr", "setenv"}
_MONITOR_CODES = {"io": "io_detected", "nondeterminism": "nondeterminism_detected"}
_DEFAULT_STATUS = {"revoked": 401, "expired": 401, "missing": 401, "forged": 401, "malformed": 400, "valid": 200}
_AUTH_PROBE_ORDER = ("valid", "malformed", "revoked", "expired", "missing", "forged")


# inherits: hd=python/honest-test/honest-test.hd::invoke_probe -> feature=specs/features/honest-test.feature::invoke_probe leaves an awaitable answer untouched -> test=python/honest-test/conformance/probe_invoke_probe_awaitable.py::probe_invoke_probe_awaitable
# inherits: hd=python/honest-test/honest-test.hd::invoke_probe -> feature=specs/features/honest-test.feature::invoke_probe propagates a callback exception -> test=python/honest-test/conformance/probe_invoke_probe_exception.py::probe_invoke_probe_exception
# inherits: hd=python/honest-test/honest-test.hd::invoke_probe -> feature=specs/features/honest-test.feature::invoke_probe returns the callback answer unchanged -> test=python/honest-test/conformance/probe_invoke_probe_identity.py::probe_invoke_probe_identity
# hd: invoke_probe
def invoke_probe(function, argument):
    """Call a supplied unary function and return its answer unchanged."""
    return function(argument)


# inherits: hd=python/honest-test/honest-test.hd::purity_findings -> feature=specs/features/honest-test.feature::purity_findings reports different answers -> test=python/honest-test/conformance/probe_purity_findings_different.py::probe_purity_findings_different
# inherits: hd=python/honest-test/honest-test.hd::purity_findings -> feature=specs/features/honest-test.feature::purity_findings returns no finding for equal answers -> test=python/honest-test/conformance/probe_purity_findings_equal.py::probe_purity_findings_equal
# hd: purity_findings
def purity_findings(first, second):
    """Report differing answers from the same link on identical inputs."""
    return _choose(
        first != second,
        [_finding("failure", "non_deterministic", "a pure link returned different results on identical input", "")],
        [],
    )


# inherits: hd=python/honest-test/honest-test.hd::mutation_findings -> feature=specs/features/honest-test.feature::mutation_findings reports a changed manifest -> test=python/honest-test/conformance/probe_mutation_findings_changed.py::probe_mutation_findings_changed
# inherits: hd=python/honest-test/honest-test.hd::mutation_findings -> feature=specs/features/honest-test.feature::mutation_findings returns no finding for equal manifests -> test=python/honest-test/conformance/probe_mutation_findings_equal.py::probe_mutation_findings_equal
# hd: mutation_findings
def mutation_findings(before, after):
    """Report the representations of a manifest before and after mutation."""
    return _choose(
        after != before,
        [_finding("failure", "manifest_mutated", f"a pure link modified its input manifest: {before!r} became {after!r}", "")],
        [],
    )


# inherits: hd=python/honest-test/honest-test.hd::idempotency_findings -> feature=specs/features/honest-test.feature::idempotency_findings reports different answers -> test=python/honest-test/conformance/probe_idempotency_findings_different.py::probe_idempotency_findings_different
# inherits: hd=python/honest-test/honest-test.hd::idempotency_findings -> feature=specs/features/honest-test.feature::idempotency_findings returns no finding for equal answers -> test=python/honest-test/conformance/probe_idempotency_findings_equal.py::probe_idempotency_findings_equal
# hd: idempotency_findings
def idempotency_findings(first, second):
    """Report differing answers from two runs of a chain on identical inputs."""
    return _choose(
        first != second,
        [_finding("failure", "not_idempotent", "a chain produced different results on identical input run twice", "")],
        [],
    )


# inherits: hd=python/honest-test/honest-test.hd::run_purity_check -> feature=specs/features/honest-test.feature::run_purity_check uses a fresh copy for each call -> test=python/honest-test/conformance/probe_run_purity_check_fresh_copies.py::probe_run_purity_check_fresh_copies
# hd: run_purity_check
def run_purity_check(link, test_manifest):
    """Run the same link on two independent copies of the supplied manifest."""
    first = invoke_probe(link, copy.deepcopy(test_manifest))
    second = invoke_probe(link, copy.deepcopy(test_manifest))
    return purity_findings(first, second)


# inherits: hd=python/honest-test/honest-test.hd::run_mutation_check -> feature=specs/features/honest-test.feature::run_mutation_check passes the original and detects its change -> test=python/honest-test/conformance/probe_run_mutation_check_original.py::probe_run_mutation_check_original
# hd: run_mutation_check
def run_mutation_check(link, test_manifest):
    """Observe whether the supplied link modifies the original manifest."""
    before = copy.deepcopy(test_manifest)
    invoke_probe(link, test_manifest)
    return mutation_findings(before, test_manifest)


# inherits: hd=python/honest-test/honest-test.hd::run_idempotency_check -> feature=specs/features/honest-test.feature::run_idempotency_check uses a fresh deep copy for each call -> test=python/honest-test/conformance/probe_run_idempotency_check_fresh_copies.py::probe_run_idempotency_check_fresh_copies
# hd: run_idempotency_check
def run_idempotency_check(chain, test_manifest):
    """Run the chain twice, each time on a fresh copy of the supplied manifest."""
    first = invoke_probe(chain, copy.deepcopy(test_manifest))
    second = invoke_probe(chain, copy.deepcopy(test_manifest))
    return idempotency_findings(first, second)


# inherits: hd=python/honest-test/honest-test.hd::verify_purity -> feature=specs/features/honest-test.feature::verify_purity runs a link twice and flags a different result -> test=python/honest-test/conformance/probe_verify_purity.py::probe_verify_purity
# hd: verify_purity
def verify_purity(link, test_manifest):
    """Return the purity check's findings for the supplied arguments."""
    return run_purity_check(link, test_manifest)


# inherits: hd=python/honest-test/honest-test.hd::detect_mutation -> feature=specs/features/honest-test.feature::detect_mutation flags a link that modified its input manifest -> test=python/honest-test/conformance/probe_detect_mutation.py::probe_detect_mutation
# hd: detect_mutation
def detect_mutation(link, test_manifest):
    """Return the mutation check's findings for the supplied arguments."""
    return run_mutation_check(link, test_manifest)


# inherits: hd=python/honest-test/honest-test.hd::test_idempotency -> feature=specs/features/honest-test.feature::test_idempotency flags a chain that is not idempotent -> test=python/honest-test/conformance/probe_test_idempotency.py::probe_test_idempotency
# hd: test_idempotency
def test_idempotency(chain, test_manifest):
    """Return the idempotency check's findings for the supplied arguments."""
    return run_idempotency_check(chain, test_manifest)


# inherits: hd=python/honest-test/honest-test.hd::read_monitored_link -> feature=specs/features/honest-test.feature::read_monitored_link propagates monitor exceptions -> test=python/honest-test/conformance/probe_read_monitored_link_exception.py::probe_read_monitored_link_exception
# inherits: hd=python/honest-test/honest-test.hd::read_monitored_link -> feature=specs/features/honest-test.feature::read_monitored_link passes the supplied link and manifest unchanged -> test=python/honest-test/conformance/probe_read_monitored_link_unchanged.py::probe_read_monitored_link_unchanged
# hd: read_monitored_link
def read_monitored_link(monitor, link, test_manifest):
    """Return the supplied monitor's observation of this link and manifest."""
    return monitor(link, test_manifest)


# inherits: hd=python/honest-test/honest-test.hd::monitor_findings -> feature=specs/features/honest-test.feature::monitor_findings allows boundary links and empty records -> test=python/honest-test/conformance/probe_monitor_findings_allowed.py::probe_monitor_findings_allowed
# inherits: hd=python/honest-test/honest-test.hd::monitor_findings -> feature=specs/features/honest-test.feature::monitor_findings reports watched calls from a non-boundary link -> test=python/honest-test/conformance/probe_monitor_findings_warning.py::probe_monitor_findings_warning
# hd: monitor_findings
def monitor_findings(link, record, kind):
    """Warn when a non-boundary link made a watched call."""
    code = _read_or(_MONITOR_CODES, kind, "io_detected")
    boundary = _read_or(link_meta(link), "boundary", False)
    return _choose(
        len(record) > 0 and not boundary,
        [_finding("warning", code, f"a non-boundary link performed a watched call: {list(record)!r}", "")],
        [],
    )


# inherits: hd=python/honest-test/honest-test.hd::run_monitor_check -> feature=specs/features/honest-test.feature::run_monitor_check judges the original manifest monitor record -> test=python/honest-test/conformance/probe_run_monitor_check.py::probe_run_monitor_check
# hd: run_monitor_check
def run_monitor_check(link, test_manifest, monitor, kind):
    """Observe the monitored link and judge the watched-call record."""
    record = read_monitored_link(monitor, link, test_manifest)
    return monitor_findings(link, record, kind)


# inherits: hd=python/honest-test/honest-test.hd::verify_under_monitor -> feature=specs/features/honest-test.feature::verify_under_monitor runs a link under the injected monitor -> test=python/honest-test/conformance/probe_verify_under_monitor.py::probe_verify_under_monitor
# hd: verify_under_monitor
def verify_under_monitor(link, test_manifest, monitor, kind):
    """Return the findings from the check using the supplied monitor."""
    return run_monitor_check(link, test_manifest, monitor, kind)


# inherits: hd=python/honest-test/honest-test.hd::server_rejection -> feature=specs/features/honest-test.feature::server_rejection recognizes only server-category faults -> test=python/honest-test/conformance/probe_server_rejection.py::probe_server_rejection
# hd: server_rejection
def server_rejection(answer):
    """Recognize only a server-category fault as a failed join."""
    return is_fault(answer) and _read_or(answer, "category", "") == "server"


# inherits: hd=python/honest-test/honest-test.hd::chain_contract_findings -> feature=specs/features/honest-test.feature::chain_contract_findings reports a failed join only for server rejection -> test=python/honest-test/conformance/probe_chain_contract_findings.py::probe_chain_contract_findings
# hd: chain_contract_findings
def chain_contract_findings(rejected):
    """Report a downstream server rejection as a chain contract failure."""
    return _choose(
        rejected,
        [_finding("failure", "chain_contract", "a downstream link rejected a valid upstream output with a server fault", "")],
        [],
    )


# inherits: hd=python/honest-test/honest-test.hd::run_chain_contract_check -> feature=specs/features/honest-test.feature::run_chain_contract_check skips upstream faults and reports downstream server rejection -> test=python/honest-test/conformance/probe_run_chain_contract_check.py::probe_run_chain_contract_check
# hd: run_chain_contract_check
def run_chain_contract_check(links, vocab, binding):
    """Probe each adjacent link join in declaration order."""
    findings = []
    for upstream, downstream in zip(links, links[1:]):
        for case in enumerate_test_cases(vocab, binding):
            answer = invoke_probe(upstream, case)
            rejected = _pick(
                is_fault(answer),
                lambda: False,
                lambda: server_rejection(invoke_probe(downstream, answer)),
            )
            findings.extend(chain_contract_findings(rejected))
    return findings


# inherits: hd=python/honest-test/honest-test.hd::test_chain_contracts -> feature=specs/features/honest-test.feature::test_chain_contracts checks each adjacent link join -> test=python/honest-test/conformance/probe_test_chain_contracts.py::probe_test_chain_contracts
# hd: test_chain_contracts
def test_chain_contracts(links, vocab, binding):
    """Return the findings from checking each adjacent link join."""
    return run_chain_contract_check(links, vocab, binding)


def compute_expected_status(token_class, fault_mapping):
    """Map one token class to the HTTP status the auth-honesty check expects (section 4.7):
    401 for revoked, expired, missing and forged, 400 for malformed by default. A provider
    may override the default by keying fault_mapping on the token class."""
    default = _read_or(_DEFAULT_STATUS, token_class, 401)
    return _read_or(fault_mapping, token_class, default)


# inherits: hd=python/honest-test/honest-test.hd::auth_probe_mode -> feature=specs/features/honest-test.feature::auth_probe_mode selects the mode for each token class -> test=python/honest-test/conformance/probe_auth_probe_mode.py::probe_auth_probe_mode
# hd: auth_probe_mode
def auth_probe_mode(token_class):
    """Select how an observation for this token class is judged."""
    match token_class:
        case "valid" | "malformed":
            return token_class
        case _:
            return "faulting"


# inherits: hd=python/honest-test/honest-test.hd::auth_probe_findings -> feature=specs/features/honest-test.feature::auth_probe_findings reports observations that violate the mode contract -> test=python/honest-test/conformance/probe_auth_probe_findings_broken.py::probe_auth_probe_findings_broken
# inherits: hd=python/honest-test/honest-test.hd::auth_probe_findings -> feature=specs/features/honest-test.feature::auth_probe_findings accepts sound observations for each mode -> test=python/honest-test/conformance/probe_auth_probe_findings_sound.py::probe_auth_probe_findings_sound
# hd: auth_probe_findings
def auth_probe_findings(token_class, mode, accepted, resolved, fault_mapping, expected):
    """Judge one auth observation according to the token's declared mode."""
    match mode:
        case "malformed":
            sound = not accepted
        case "valid":
            sound = accepted and _is_ok(resolved)
        case _:
            failure = _pick(accepted and hasattr(resolved, "get"), lambda: _err_fault(resolved), lambda: None)
            sound = failure is not None and _read_or(
                fault_mapping, _read_or(failure, "category", ""), None
            ) == expected
    return _choose(
        sound,
        [],
        [_finding("failure", "auth_honesty", f"the provider mishandled the {token_class} token class", "")],
    )


# inherits: hd=python/honest-test/honest-test.hd::run_auth_honesty_check -> feature=specs/features/honest-test.feature::run_auth_honesty_check propagates unexpected callback errors -> test=python/honest-test/conformance/probe_run_auth_honesty_check_exception.py::probe_run_auth_honesty_check_exception
# inherits: hd=python/honest-test/honest-test.hd::run_auth_honesty_check -> feature=specs/features/honest-test.feature::run_auth_honesty_check probes token classes in order and resolves only eligible tokens -> test=python/honest-test/conformance/probe_run_auth_honesty_check_ordered.py::probe_run_auth_honesty_check_ordered
# hd: run_auth_honesty_check
def run_auth_honesty_check(provider):
    """Collect observations from the provider in the declared token probe order."""
    generate = provider["test_token_generator"]
    recognizer = provider["actor_recognizer"]
    resolve = provider["resolve_actor"]
    fault_mapping = provider["fault_mapping"]
    findings = []
    for token_class in _AUTH_PROBE_ORDER:
        mode = auth_probe_mode(token_class)
        token = invoke_probe(generate, token_class)
        accepted = bool(invoke_probe(recognizer, token))
        resolved = _pick(accepted and mode != "malformed", lambda: invoke_probe(resolve, token), lambda: None)
        expected = compute_expected_status(token_class, fault_mapping)
        findings.extend(auth_probe_findings(token_class, mode, accepted, resolved, fault_mapping, expected))
    return findings


# inherits: hd=python/honest-test/honest-test.hd::test_auth_honesty -> feature=specs/features/honest-test.feature::test_auth_honesty probes a provider with each token class -> test=python/honest-test/conformance/probe_test_auth_honesty.py::probe_test_auth_honesty
# hd: test_auth_honesty
def test_auth_honesty(provider):
    """Return the auth-honesty findings for the supplied provider."""
    return run_auth_honesty_check(provider)


def check_gate_honesty(gates):
    """Verify every declared gate names a proof-of-failure test (section 4.9): a gate with
    no proof is gate_unverified, a proof that asserts only that some exception was raised
    rather than binding the specific failure is gate_proof_unbound."""
    def _gate_findings(gate):
        proof = _read_or(gate, "proof", None)
        return _pick(
            proof is None,
            lambda: [_finding("rejection", "gate_unverified", f"gate {gate['name']!r} names no proof-of-failure test", gate["location"])],
            lambda: _choose(
                proof["binds_failure"],
                [],
                [_finding("rejection", "gate_proof_unbound", f"gate {gate['name']!r} has a proof that does not bind the specific failure", gate["location"])],
            ),
        )

    return [found for gate in gates for found in _gate_findings(gate)]


# inherits: hd=python/honest-test/honest-test.hd::body_findings -> feature=specs/features/honest-test.feature::body_findings returns empty for an honest test body -> test=python/honest-test/conformance/probe_body_findings_honest.py::probe_body_findings_honest
# inherits: hd=python/honest-test/honest-test.hd::body_findings -> feature=specs/features/honest-test.feature::body_findings reports one rejection per runtime rebinding -> test=python/honest-test/conformance/probe_body_findings_rebindings.py::probe_body_findings_rebindings
# hd: body_findings
def body_findings(root):
    """Return one rejection per statement that rebinds a call target at runtime (section
    4.8): a monkeypatch fixture, a mock.patch, a setattr on an imported symbol, or an
    imported symbol rebound by attribute assignment. An honest body returns the empty list."""
    def _call_is_rebind(text):
        tokens = text.split(".")
        monkey = len(tokens) >= 2 and tokens[0] == "monkeypatch" and tokens[-1] in _REBIND_METHODS
        bare = text in {"setattr", "delattr"}
        return monkey or bare or "patch" in tokens

    def _is_rebind_call(call):
        function = call.child_by_field_name("function")
        return _pick(function is None, lambda: False, lambda: _call_is_rebind(function.text.decode("utf-8")))

    def _is_attr_assignment(assignment):
        left = assignment.child_by_field_name("left")
        return left is not None and left.type == "attribute"

    def _rebind_rejection(node):
        row, col = line_col(node)
        return _finding(
            "rejection",
            "test_body_dishonest",
            "a test body rebinds a call target at runtime; pass the dependency as a parameter, or inject a boundary plug as an argument, instead",
            f"{row}:{col}",
        )

    nodes = walk(root)
    rebind_calls = filter(_is_rebind_call, filter(lambda n: n.type == "call", nodes))
    attr_assignments = filter(_is_attr_assignment, filter(lambda n: n.type == "assignment", nodes))
    sites = list(rebind_calls) + list(attr_assignments)
    return [_rebind_rejection(node) for node in sites]


# inherits: hd=python/honest-test/honest-test.hd::test_body_violations -> feature=specs/features/honest-test.feature::test_body_violations returns one rejection per runtime rebinding -> test=python/honest-test/conformance/probe_test_body_violations.py::probe_test_body_violations
# hd: test_body_violations
def test_body_violations(source):
    """Return the runtime-rebinding findings for the supplied source text."""
    from honest_test.io_boundary import run_body_check

    return run_body_check(source)
