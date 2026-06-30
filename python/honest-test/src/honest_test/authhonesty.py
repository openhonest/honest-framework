"""Authentication honesty testing (section 4.7): the boundary validator must resolve every token class correctly.

A provider's correctness claim is only as strong as the behaviours its contract covers. honest-test probes
the registered provider's boundary validator — `resolve_actor` — with the token classes, the smallest set
that exercises the contract, and asserts each produces its declared outcome. A change that, say, starts
accepting expired tokens fails this test even though nothing downstream changed; without it, that regression
would only surface in an end-to-end test against the deployed application.

The pure surface is honest-test's: the token classes, the fault-to-HTTP map, the default class-to-status
expectations (overridable by the provider), and the per-class decision. The provider is injected —
`{"generate": class -> token, "actor_recognizer": token -> bool, "resolve_actor": token -> result,
"fault_mapping": {category: status}, "name": str}` — so honest-test never imports honest-auth; the harness
wires the real provider in. Whether a resolved actor is authorized for a particular target is ordinary link
logic, tested by that link, not here.
"""

from honest_test.honesty import _finding

# The token classes (section 4.7): the smallest set that exercises a boundary validator.
_AUTH_CLASSES = ("valid", "revoked", "expired", "malformed", "missing", "forged")

# The default class-to-outcome expectations (section 4.7), overridable by a provider's fault_mapping.
_DEFAULT_EXPECTED = {
    "valid": "ok",
    "revoked": 401,
    "expired": 401,
    "malformed": 400,
    "missing": 401,
    "forged": 401,
}

# A fault category to its HTTP status: the auth categories plus the framework's client/server.
_FAULT_HTTP = {"forbidden": 403, "unauthenticated": 401, "client": 400, "server": 500}


def auth_token_classes():
    """The token classes an authentication honesty test exercises (section 4.7). Pure."""
    return list(_AUTH_CLASSES)


def map_fault_to_http(fault):
    """The HTTP status a fault maps to, by its category (section 4.7): a forbidden fault is 403, an
    unauthenticated one 401, a client fault 400, anything else 500. Pure."""
    return _FAULT_HTTP.get(fault["category"], 500)


def auth_expected_status(class_name, fault_mapping=None):
    """The expected outcome for a token class (section 4.7): `"ok"` for a valid token, else the HTTP status it
    must fault with — the default mapping, overridden by the provider's fault_mapping where it sets a class.
    Pure."""
    return (fault_mapping or {}).get(class_name, _DEFAULT_EXPECTED[class_name])


def auth_honesty_finding(subject, class_name, result, expected):
    """The per-class decision for a `resolve_actor` result (section 4.7): a valid token must resolve (ok);
    every fault class must err with the expected HTTP status. Returns a finding on a dishonest outcome, else
    None. Pure."""
    if expected == "ok":
        if "ok" in result:
            return None
        return _finding("auth_honesty", subject, f"rejected a valid token: {result}")
    if "err" in result and map_fault_to_http(result["err"]) == expected:
        return None
    return _finding("auth_honesty", subject, f"did not fault correctly for token class '{class_name}': expected {expected}, got {result}")


def test_auth_honesty(provider):
    """Run the authentication honesty test on the registered provider (section 4.7): for each token class
    generate a token and probe the boundary validator — a malformed token must be rejected by the
    `actor_recognizer`; every other class is passed to `resolve_actor` and its outcome checked against the
    class's expectation. Returns the findings for the classes that behaved dishonestly. A no-op when no
    provider is registered (HC-A001 covers that). The provider is injected, so this never imports honest-auth."""
    if provider is None:
        return []
    fault_mapping = provider.get("fault_mapping", {})
    subject = provider.get("name", "auth")
    findings = []
    for class_name in _AUTH_CLASSES:
        token = provider["generate"](class_name)
        expected = auth_expected_status(class_name, fault_mapping)
        if class_name == "malformed":
            if provider["actor_recognizer"](token):
                findings.append(_finding("auth_honesty", subject, "accepted a malformed token at the recognizer"))
            continue
        result = provider["resolve_actor"](token)
        finding = auth_honesty_finding(subject, class_name, result, expected)
        if finding is not None:
            findings.append(finding)
    return findings
