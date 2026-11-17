"""The honesty, chain-contract, auth, gate and test-body checks (spec sections 4.1
through 4.9). Each is pure: it runs injected callables or reads data and returns a list
of Findings as data, never raising. A Finding carries a kind, a code, a message and a
location.
"""

import copy

from honest_parse import line_col, parse, walk
from honest_type import is_fault

from honest_test._util import _choose, _pick, _read_or
from honest_test.generate import enumerate_test_cases

_finding = lambda kind, code, message, location: {"kind": kind, "code": code, "message": message, "location": location}
_is_ok = lambda result: hasattr(result, "get") and "ok" in result
_err_fault = lambda result: _read_or(result, "err", None)

_REBIND_METHODS = {"setattr", "setitem", "delattr", "setenv"}
_MONITOR_CODES = {"io": "io_detected", "nondeterminism": "nondeterminism_detected"}
_DEFAULT_STATUS = {"revoked": 401, "expired": 401, "missing": 401, "forged": 401, "malformed": 400, "valid": 200}


def verify_purity(link, test_manifest):
    """Run the link twice on the same manifest and fault non_deterministic when the two
    results differ (section 4.1): a pure function returns the same output for the same
    input, always."""
    first = link(copy.deepcopy(test_manifest))
    second = link(copy.deepcopy(test_manifest))
    return _choose(
        first != second,
        [_finding("failure", "non_deterministic", "a pure link returned different results on identical input", "")],
        [],
    )


def detect_mutation(link, test_manifest):
    """Deep-copy the manifest, run the link, and fault manifest_mutated when the manifest
    after the run differs from the copy taken before (section 4.2): a pure function must
    not modify its input."""
    before = copy.deepcopy(test_manifest)
    link(test_manifest)
    return _choose(
        test_manifest != before,
        [_finding("failure", "manifest_mutated", f"a pure link modified its input manifest: {before!r} became {test_manifest!r}", "")],
        [],
    )


def test_idempotency(chain, test_manifest):
    """Run the chain twice, the second time on a deep copy, and fault not_idempotent when
    the two results differ (section 4.3): the same chain on the same manifest must produce
    the same result."""
    first = chain(copy.deepcopy(test_manifest))
    second = chain(copy.deepcopy(test_manifest))
    return _choose(
        first != second,
        [_finding("failure", "not_idempotent", "a chain produced different results on identical input run twice", "")],
        [],
    )


def verify_under_monitor(link, test_manifest, monitor, kind):
    """Run the link inside the injected monitor and warn when the monitor recorded a watched
    call on a non-boundary link (sections 4.4, 4.5): io_detected for kind io,
    nondeterminism_detected for kind nondeterminism. The warning reports and does not
    block."""
    record = monitor(link, test_manifest)
    code = _read_or(_MONITOR_CODES, kind, "io_detected")
    return _choose(
        len(record) > 0,
        [_finding("warning", code, f"a non-boundary link performed a watched call: {list(record)!r}", "")],
        [],
    )


def test_chain_contracts(links, vocab, binding):
    """Check each adjacent link join (section 4.6): enumerate the upstream link's inputs,
    run it, feed each ok manifest to the downstream link, and fault chain_contract when the
    downstream link rejects a valid output with a server fault. A client fault is not a
    contract failure."""
    pairs = list(zip(links, links[1:]))

    def _server_rejects(down, manifest):
        result = down(manifest)
        return _pick(is_fault(result), lambda: _read_or(result, "category", "") == "server", lambda: False)

    def _join_failures(pair):
        up, down = pair
        out = []
        for case in enumerate_test_cases(vocab, binding):
            output = up(case)
            failed = _pick(is_fault(output), lambda: False, lambda: _server_rejects(down, output))
            out.extend(_choose(failed, [_finding("failure", "chain_contract", "a downstream link rejected a valid upstream output with a server fault", "")], []))
        return out

    return [found for pair in pairs for found in _join_failures(pair)]


def compute_expected_status(token_class, fault_mapping):
    """Map one token class to the HTTP status the auth-honesty check expects (section 4.7):
    401 for revoked, expired, missing and forged, 400 for malformed by default. A provider
    may override the default by keying fault_mapping on the token class."""
    default = _read_or(_DEFAULT_STATUS, token_class, 401)
    return _read_or(fault_mapping, token_class, default)


def test_auth_honesty(provider):
    """Probe a provider with each of the six token classes and fault auth_honesty when it
    accepts a malformed token at the recognizer, rejects a valid one, or does not fault
    correctly for a class (section 4.7)."""
    generate = provider["test_token_generator"]
    recognizer = provider["actor_recognizer"]
    resolve = provider["resolve_actor"]
    fault_mapping = provider["fault_mapping"]

    def _fault_matches(token_class, token):
        fault = _err_fault(resolve(token))
        mapped = _pick(fault is None, lambda: None, lambda: _read_or(fault_mapping, _read_or(fault, "category", ""), None))
        return mapped == compute_expected_status(token_class, fault_mapping)

    checks = {
        "valid": lambda token_class, token, accepted: accepted and _is_ok(resolve(token)),
        "malformed": lambda token_class, token, accepted: not accepted,
        "faulting": lambda token_class, token, accepted: accepted and _fault_matches(token_class, token),
    }
    mode = {"valid": "valid", "malformed": "malformed", "revoked": "faulting", "expired": "faulting", "missing": "faulting", "forged": "faulting"}

    def _class_findings(token_class):
        token = generate(token_class)
        accepted = bool(recognizer(token))
        sound = checks[mode[token_class]](token_class, token, accepted)
        return _choose(sound, [], [_finding("failure", "auth_honesty", f"the provider mishandled the {token_class} token class", "")])

    return [found for token_class in mode for found in _class_findings(token_class)]


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


def test_body_violations(source):
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

    nodes = walk(parse(source.encode("utf-8"), "python").root_node)
    rebind_calls = filter(_is_rebind_call, filter(lambda n: n.type == "call", nodes))
    attr_assignments = filter(_is_attr_assignment, filter(lambda n: n.type == "assignment", nodes))
    sites = list(rebind_calls) + list(attr_assignments)
    return [_rebind_rejection(node) for node in sites]
