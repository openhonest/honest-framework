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
    expected = ["AuthProvider", "Registry", "empty_registry", "register_auth_provider", "registered_provider", "validate_provider", "authenticate", "fault_status", "authentication_honesty", "resolve_actor_deterministic", "dev_auth_provider"]
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
    # A missing credential (None / empty) is unauthenticated, not malformed (section 2.4), and never
    # reaches the recognizer or resolver.
    for absent in (None, ""):
        mf = authenticate(prov, absent).get("err", {})
        if mf.get("category") != "unauthenticated" or mf.get("code") != "unauthenticated" or mf.get("message") != "no credential was presented at the boundary":
            bad.append(f"a missing credential ({absent!r}) should be unauthenticated, before the recognizer: {mf}")
    return bad


def _law_dev_provider():
    from honest_auth import authentication_honesty, dev_auth_provider, validate_provider

    bad = []
    dev = dev_auth_provider({"alice": "secret", "bob": ""})
    if "ok" not in validate_provider(dev):
        bad.append("the dev provider should be a valid AuthProvider")
    if "ok" not in authentication_honesty(dev, None):
        bad.append(f"the dev provider should be authentication-honest: {authentication_honesty(dev, None)}")
    # A real user with a matching password resolves; a wrong password fails.
    if authenticate(dev, "alice:secret") != ok({"id": "alice"}):
        bad.append(f"a correct username:password should resolve to the actor: {authenticate(dev, 'alice:secret')}")
    if authenticate(dev, "alice:wrong").get("err", {}).get("category") != "unauthenticated":
        bad.append("a wrong password should be unauthenticated")
    # Requirement 2: a user whose stored password is empty accepts ANY password (dev convenience).
    if authenticate(dev, "bob:anything-at-all") != ok({"id": "bob"}) or authenticate(dev, "bob:") != ok({"id": "bob"}):
        bad.append(f"an empty stored password should accept any password: {authenticate(dev, 'bob:anything-at-all')}")
    # An unknown user, a malformed token, and a missing credential each fail as the class expects.
    if authenticate(dev, "ghost:x").get("err", {}).get("category") != "unauthenticated":
        bad.append("an unknown user should be unauthenticated")
    if authenticate(dev, "nocolon").get("err", {}).get("code") != "malformed_token":
        bad.append("a token with no colon is malformed at the recognizer")
    if authenticate(dev, None).get("err", {}).get("category") != "unauthenticated":
        bad.append("a missing credential is unauthenticated")
    # Requirement 1: the default table is a single dev user with an empty password — log in with anything.
    default_dev = dev_auth_provider(None)
    if authenticate(default_dev, "dev:whatever") != ok({"id": "dev"}):
        bad.append(f"the default dev provider should log in the 'dev' user with any password: {authenticate(default_dev, 'dev:whatever')}")
    if dev["name"] != "dev-plaintext":
        bad.append(f"the dev provider is named dev-plaintext: {dev['name']}")
    # An empty username (no name before the colon) is malformed at the recognizer, not an unknown user.
    if authenticate(dev, ":secret").get("err", {}).get("code") != "malformed_token":
        bad.append("a token with an empty username should be malformed at the recognizer")
    # The resolver faults carry their own code and message, distinct per cause.
    ghost = authenticate(dev, "ghost:x").get("err", {})
    if ghost.get("code") != "forged" or ghost.get("message") != "no such dev user":
        bad.append(f"an unknown dev user should fault as forged: {ghost}")
    wrong = authenticate(dev, "alice:wrong").get("err", {})
    if wrong.get("code") != "bad_password" or wrong.get("message") != "wrong password for the dev user":
        bad.append(f"a wrong password should fault as bad_password: {wrong}")
    # The generator: the valid token targets the first user; malformed is unrecognised; missing is None;
    # and revoked/expired/forged are each recognised (real wire format) yet resolve unauthenticated via
    # the resolver — not via the missing-credential guard, which an empty token would hit instead.
    gen, recognises = dev["test_token_generator"], dev["actor_recognizer"]
    if gen("valid", None) != "alice:secret":
        bad.append(f"the valid test token should target the first user: {gen('valid', None)}")
    if recognises(gen("malformed", None)):
        bad.append("the malformed test token should be rejected by the recognizer")
    if gen("missing", None) is not None:
        bad.append("the missing test token should be a None credential")
    for cls in ("revoked", "expired", "forged"):
        token = gen(cls, None)
        if not recognises(token) or authenticate(dev, token).get("err", {}).get("category") != "unauthenticated":
            bad.append(f"the {cls} test token should be recognised yet resolve unauthenticated: {token!r}")
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


# A synthetic application (section 9.2): a boundary that resolves an actor from the request's token and
# passes it inward as data, and an interior operation that takes the manifest only. The interior never
# receives the request, so it has nothing to read an actor out of — the shape the law below proves.
def _synthetic_boundary(provider, request):
    """The boundary: authenticate the request's token and put the resolved actor in the manifest."""
    resolved = authenticate(provider, request["token"])
    return {"actor": resolved["ok"]} if "ok" in resolved else {"fault": resolved["err"]["code"]}


def _synthetic_interior(manifest):
    """An interior operation: pure over the manifest it is handed. It takes no request."""
    return f"profile of {manifest['actor']}"


def _law_actor_reaches_interior_as_data():
    """Section 9.2: the resolved actor reaches the interior as data, and no operation reads an actor from
    request input. The first half is checked by value — the actor the boundary resolved is the actor the
    interior receives. The second is checked by falsification rather than assertion: the interior is run
    again with the same manifest while the request is changed out from under it, and its result must not
    move. An interior that reached back into the request for an actor would answer differently."""
    bad = []
    provider = _honest_provider()
    manifest = _synthetic_boundary(provider, {"token": "good"})
    if manifest != {"actor": "alice"}:
        bad.append(f"the boundary must resolve the actor and pass it inward as data: {manifest}")
    if _synthetic_interior(manifest) != "profile of alice":
        bad.append("the interior must receive the resolved actor as data")
    # Change the request entirely; the interior sees only the manifest, so its answer cannot move.
    _synthetic_boundary(provider, {"token": "bad"})
    if _synthetic_interior(manifest) != "profile of alice":
        bad.append("the interior must not depend on request input — it answered differently after the request changed")
    # A rejected token yields no actor at all, so nothing downstream can proceed with one. "bad" fails
    # the recognizer, so it is refused as malformed before the resolver is ever consulted.
    rejected = _synthetic_boundary(provider, {"token": "bad"})
    if "actor" in rejected or rejected.get("fault") != "malformed_token":
        bad.append(f"a rejected token must yield a fault and no actor: {rejected}")
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
    "actor_reaches_interior_as_data": _law_actor_reaches_interior_as_data,
    "dev_provider": _law_dev_provider,
}


def run():
    violations = {name: law() for name, law in _LAWS.items()}
    failed = {name: msgs for name, msgs in violations.items() if msgs}
    passed = len(_LAWS) - len(failed)
    for name, msgs in failed.items():
        print(f"FAIL HA-law [{name}]: {msgs}")
    print(f"HA laws: {passed} passed, {len(failed)} failed, {len(_LAWS)} total")
    return 0 if not failed else 1
