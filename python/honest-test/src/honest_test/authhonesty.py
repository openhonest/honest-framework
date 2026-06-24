"""Auth honesty testing (section 4.7): an authorizing link must fault correctly for every token class.

A provider's correctness claim is only as strong as the behaviours its contract covers. For every link
declared `authorizes=True`, honest-test exercises the seven token classes — the smallest set that probes
the contract — and asserts each produces its declared outcome. A change to an authorizing link that, say,
starts accepting expired tokens fails this test even though the link's output shape is unchanged; without
it, that regression would only surface in an end-to-end test against the deployed application.

The pure surface is honest-test's: the seven classes, the fault-to-HTTP map, the default class-to-status
expectations (overridable by the provider), and the per-class decision. The token generator and the chain
run are injected — the provider is `{"generate": class -> token, "fault_mapping": {class: status}}` and
`run` maps a token to the chain result — so honest-test never imports honest-auth; the harness wires the
real provider and execution in.
"""

from honest_type.chains import link_meta

from honest_test.honesty import _finding, _name

# The seven token classes (section 4.7): the smallest set that exercises an authorization contract.
_AUTH_CLASSES = ("valid_authorized", "valid_unauthorized", "revoked", "expired", "malformed", "missing", "forged")

# The default class-to-outcome expectations (section 4.7), overridable by a provider's fault_mapping.
_DEFAULT_EXPECTED = {
    "valid_authorized": "ok",
    "valid_unauthorized": 403,
    "revoked": 401,
    "expired": 401,
    "malformed": 400,
    "missing": 401,
    "forged": 401,
}

# A fault category to its HTTP status: the auth guard categories plus the framework's client/server.
_FAULT_HTTP = {"forbidden": 403, "unauthenticated": 401, "client": 400, "server": 500}


def auth_token_classes():
    """The seven token classes an auth honesty test exercises (section 4.7). Pure."""
    return list(_AUTH_CLASSES)


def map_fault_to_http(fault):
    """The HTTP status a fault maps to, by its category (section 4.7): a forbidden guard fault is 403, an
    unauthenticated one 401, a client fault 400, anything else 500. Pure."""
    return _FAULT_HTTP.get(fault["category"], 500)


def auth_expected_status(class_name, fault_mapping=None):
    """The expected outcome for a token class (section 4.7): `"ok"` for a valid authorized token, else the
    HTTP status it must fault with — the default mapping, overridden by the provider's fault_mapping where
    it sets a class. Pure."""
    return (fault_mapping or {}).get(class_name, _DEFAULT_EXPECTED[class_name])


def auth_honesty_finding(link_name, class_name, result, expected):
    """The per-class decision (section 4.7): a valid authorized token must be accepted (ok); every other
    class must fault with the expected HTTP status. Returns a finding on a dishonest outcome, else None.
    Pure."""
    if expected == "ok":
        if "ok" in result:
            return None
        return _finding("auth_honesty", link_name, f"Link rejected a valid authorized token: {result}")
    if "err" in result and map_fault_to_http(result["err"]) == expected:
        return None
    return _finding("auth_honesty", link_name, f"Link did not fault correctly for token class '{class_name}': expected {expected}, got {result}")


def test_auth_honesty(link, provider, run):
    """Run the auth honesty test on an authorizing link (section 4.7): for each of the seven token classes
    generate a token through the provider, run the chain on it, and check the outcome against the class's
    expectation. Returns the findings for the classes that behaved dishonestly. A no-op when no provider is
    registered (HC-A001 covers that) or the link does not authorize. The provider's generator and the
    chain run are injected, so this never imports honest-auth."""
    if provider is None or not link_meta(link).get("authorizes"):
        return []
    fault_mapping = provider.get("fault_mapping", {})
    findings = []
    for class_name in _AUTH_CLASSES:
        token = provider["generate"](class_name)
        result = run(token)
        finding = auth_honesty_finding(_name(link), class_name, result, auth_expected_status(class_name, fault_mapping))
        if finding is not None:
            findings.append(finding)
    return findings
