"""The authentication-honesty contract as executable checks (section 4.7).

A provider proves it honours the token-class contract (section 4.2): a valid token resolves to an
actor, a malformed one is rejected at the recognizer before `resolve_actor`, and every other class
fails as unauthenticated — no valid identity. `authentication_honesty` runs the provider's own
`test_token_generator` across the classes and checks each outcome; `resolve_actor_deterministic`
confirms a token resolves the same way twice (section 4.4). Pure over the provider's injected generator
and resolver — no mocks, the provider proves itself.
"""

from honest_type import err, fault, ok

from honest_auth.authenticate import authenticate

# The six token classes every provider's test_token_generator produces (section 2.4).
_TOKEN_CLASSES = ("valid", "revoked", "expired", "malformed", "missing", "forged")

# The outcome authenticate() must produce for a token of each class (section 4.2): an actor for a valid
# token, a recognizer rejection for a malformed one, and an unauthenticated fault for the rest.
_EXPECTED = {
    "valid": "actor",
    "malformed": "recognizer_reject",
    "revoked": "unauthenticated",
    "expired": "unauthenticated",
    "missing": "unauthenticated",
    "forged": "unauthenticated",
}


def _outcome(result):
    """Classify what authenticate() produced (section 4.2): 'actor' for ok, 'recognizer_reject' when the
    recognizer rejected the token before resolution, else the fault's category. Pure."""
    if "ok" in result:
        return "actor"
    if result["err"]["code"] == "malformed_token":
        return "recognizer_reject"
    return result["err"]["category"]


def authentication_honesty(provider, context):
    """Check a provider honours the token-class contract (sections 4.2, 4.7): run its
    test_token_generator across every class and confirm authenticate() produces the outcome the class
    names. Returns ok(provider), or err(authentication_dishonest) listing each class whose outcome was
    wrong with its expected and actual outcome. Pure over the provider's injected generator and
    resolver — the provider proves itself, nothing is mocked."""
    violations = []
    for class_name in _TOKEN_CLASSES:
        outcome = _outcome(authenticate(provider, provider["test_token_generator"](class_name, context)))
        if outcome != _EXPECTED[class_name]:
            violations.append({"class": class_name, "expected": _EXPECTED[class_name], "got": outcome})
    if violations:
        return err(fault("authentication_dishonest", "the provider does not honour the token-class contract", "server", detail=violations))
    return ok(provider)


def resolve_actor_deterministic(provider, token):
    """Whether the provider resolves a token the same way twice under fixed backing state (section 4.4):
    it runs the boundary resolution twice and reports whether the two results agree. Pure over the
    injected resolver."""
    return authenticate(provider, token) == authenticate(provider, token)
