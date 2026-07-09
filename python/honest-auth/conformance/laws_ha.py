"""honest-auth conformance laws: the registry, provider validation, the boundary flow, and fault mapping.

These exercise the functions across every branch, including the ones that take live callables (a provider's
recognizer and resolver), which the portable suite.json value cases cannot carry. Pure assertions:
data in, data out.
"""

from honest_auth import (
    authenticate,
    empty_registry,
    fault_status,
    register_auth_provider,
    registered_provider,
    validate_provider,
)
from honest_type import err, fault, ok


def _provider(recognizer=None, resolver=None, fault_mapping=None):
    return {
        "name": "p",
        "actor_recognizer": recognizer or (lambda token: token != "bad"),
        "resolve_actor": resolver or (lambda token: ok("actor") if token == "good" else err(fault("nope", "no", "unauthenticated"))),
        "test_token_generator": lambda class_name, context: class_name,
        "fault_mapping": fault_mapping or {},
    }


# A real, minimal conforming provider (section 5.3 style, not a mock): each token class maps to a token
# its recognizer and resolver handle so the class's outcome is correct — 'good' resolves to an actor,
# 'bad' is malformed (recognizer rejects), and every other class resolves to an unauthenticated fault.
def _honest_provider():
    return {
        "name": "honest",
        "actor_recognizer": lambda token: token != "bad",
        "resolve_actor": lambda token: ok("alice") if token == "good" else err(fault(token, "no valid identity", "unauthenticated")),
        "test_token_generator": lambda class_name, context: {"valid": "good", "malformed": "bad"}.get(class_name, class_name),
        "fault_mapping": {},
    }


# A dishonest provider: its resolver hands an actor back for every recognized token, so revoked, expired,
# missing, and forged tokens all wrongly resolve to an actor instead of failing as unauthenticated.
def _dishonest_provider():
    return {
        "name": "dishonest",
        "actor_recognizer": lambda token: token != "bad",
        "resolve_actor": lambda token: ok("alice"),
        "test_token_generator": lambda class_name, context: {"valid": "good", "malformed": "bad"}.get(class_name, class_name),
        "fault_mapping": {},
    }


_MISSING_FOUR = ["actor_recognizer", "resolve_actor", "test_token_generator", "fault_mapping"]
_MISSING_MESSAGE = f"AuthProvider is missing required fields: {_MISSING_FOUR}"


def _law_exports():
    import honest_auth

    bad = []
    expected = ["AuthProvider", "Registry", "empty_registry", "register_auth_provider", "registered_provider", "validate_provider", "authenticate", "fault_status", "authentication_honesty", "resolve_actor_deterministic"]
    if sorted(getattr(honest_auth, "__all__", [])) != sorted(expected):
        bad.append(f"__all__ should be exactly the public surface: {getattr(honest_auth, '__all__', None)}")
    missing = [name for name in expected if not hasattr(honest_auth, name)]
    if missing:
        bad.append(f"__all__ names not importable: {missing}")
    return bad


def _law_empty_registry():
    bad = []
    if empty_registry() != {"provider": None}:
        bad.append(f"empty_registry should hold no provider: {empty_registry()}")
    return bad


def _law_validate_provider():
    bad = []
    if "ok" not in validate_provider(_provider()):
        bad.append("a complete provider should validate")
    f = validate_provider({"name": "x"}).get("err", {})
    if f.get("code") != "invalid_provider" or f.get("category") != "client" or f.get("detail") != _MISSING_FOUR:
        bad.append(f"a provider missing fields should be invalid_provider listing them: {f}")
    if f.get("message") != _MISSING_MESSAGE:
        bad.append(f"invalid_provider message wrong: {f.get('message')}")
    return bad


def _law_register_auth_provider():
    bad = []
    reg = register_auth_provider(empty_registry(), _provider())
    if "ok" not in reg or registered_provider(reg["ok"])["name"] != "p":
        bad.append(f"registering a valid provider should hold it: {reg}")
    sf = register_auth_provider(reg["ok"], _provider()).get("err", {})
    if sf.get("code") != "already_registered" or sf.get("category") != "client" or sf.get("message") != "an AuthProvider is already registered for this application":
        bad.append(f"a second registration should be already_registered: {sf}")
    if register_auth_provider(empty_registry(), {"name": "x"}).get("err", {}).get("code") != "invalid_provider":
        bad.append("registering a malformed provider should be invalid_provider")
    base = empty_registry()
    register_auth_provider(base, _provider())
    if base["provider"] is not None:
        bad.append("register_auth_provider must not mutate its argument (the registry is a value)")
    return bad


def _law_registered_provider():
    bad = []
    if registered_provider(empty_registry()) is not None:
        bad.append("an empty registry has no provider")
    if registered_provider({"provider": {"name": "q"}}) != {"name": "q"}:
        bad.append("registered_provider returns the held provider")
    return bad


def _law_authenticate():
    bad = []
    prov = _provider()
    if authenticate(prov, "good") != ok("actor"):
        bad.append("a recognised valid token resolves to its actor")
    rf = authenticate(prov, "bad").get("err", {})
    if rf.get("category") != "client" or rf.get("code") != "malformed_token" or rf.get("message") != "token does not match the provider's wire format":
        bad.append(f"a malformed token is rejected at the recognizer (client), before resolve_actor: {rf}")
    if authenticate(prov, "other").get("err", {}).get("category") != "unauthenticated":
        bad.append("a recognised but invalid token faults via resolve_actor")
    return bad


def _law_fault_status():
    bad = []
    default = _provider()
    for category, status in {"unauthenticated": 401, "forbidden": 403, "conflict": 409, "client": 400, "server": 500}.items():
        if fault_status(default, {"category": category}) != status:
            bad.append(f"default status for {category} should be {status}: {fault_status(default, {'category': category})}")
    if fault_status(default, {"category": "weird"}) != 500:
        bad.append("an unknown category falls back to 500")
    if fault_status(_provider(fault_mapping={"unauthenticated": 419}), {"category": "unauthenticated"}) != 419:
        bad.append("the provider fault_mapping overrides the default status")
    return bad


def _law_authentication_honesty():
    from honest_auth import authentication_honesty

    bad = []
    if "ok" not in authentication_honesty(_honest_provider(), None):
        bad.append(f"an honest provider should pass the authentication-honesty check: {authentication_honesty(_honest_provider(), None)}")
    dishonest = authentication_honesty(_dishonest_provider(), None)
    if "err" not in dishonest or dishonest["err"]["code"] != "authentication_dishonest" or dishonest["err"]["category"] != "server" or dishonest["err"]["message"] != "the provider does not honour the token-class contract":
        bad.append(f"a provider that resolves revoked/forged tokens to an actor should be authentication_dishonest: {dishonest}")
    else:
        classes = {v["class"] for v in dishonest["err"]["detail"]}
        if classes != {"revoked", "expired", "missing", "forged"}:
            bad.append(f"the violation should name each dishonest class (got an actor, expected unauthenticated): {classes}")
        got = {v["class"]: (v["expected"], v["got"]) for v in dishonest["err"]["detail"]}
        if got.get("forged") != ("unauthenticated", "actor"):
            bad.append(f"each violation should carry the expected and actual outcome: {got.get('forged')}")
    return bad


def _law_resolve_actor_deterministic():
    from honest_auth import resolve_actor_deterministic

    bad = []
    if not resolve_actor_deterministic(_honest_provider(), "good"):
        bad.append("a resolver that returns the same result for a token should be reported deterministic")
    calls = []

    def flaky(token):
        calls.append(1)
        return ok("a") if len(calls) % 2 == 0 else err(fault("x", "y", "unauthenticated"))

    if resolve_actor_deterministic(_provider(resolver=flaky), "good"):
        bad.append("a resolver that returns different results for the same token is not deterministic")
    return bad


_LAWS = {
    "exports": _law_exports,
    "empty_registry": _law_empty_registry,
    "validate_provider": _law_validate_provider,
    "register_auth_provider": _law_register_auth_provider,
    "registered_provider": _law_registered_provider,
    "authenticate": _law_authenticate,
    "fault_status": _law_fault_status,
    "authentication_honesty": _law_authentication_honesty,
    "resolve_actor_deterministic": _law_resolve_actor_deterministic,
}


def run():
    violations = {name: law() for name, law in _LAWS.items()}
    failed = {name: msgs for name, msgs in violations.items() if msgs}
    passed = len(_LAWS) - len(failed)
    for name, msgs in failed.items():
        print(f"FAIL HA-law [{name}]: {msgs}")
    print(f"HA laws: {passed} passed, {len(failed)} failed, {len(_LAWS)} total")
    return 0 if not failed else 1
