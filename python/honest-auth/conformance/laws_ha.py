"""honest-auth conformance laws: the plugin contract, the value registry, the boundary flow, and the
executable authentication-honesty verifier, each exercised over a synthetic provider built here.

honest-auth owns no world: every function is pure composition over a provider's injected callables
(honest-auth-architecture.md §1, §2). So these laws build one synthetic AuthProvider — a recognizer, a
resolver, a token generator and a fault mapping — and drive the real functions through it: registration
and its two failures (§3), the boundary flow's two paths (§2.2, §2.3), the per-class outcome table
(§4.7), the honesty verifier on an honest and a dishonest provider (§4.7), the determinism check (§4.4),
and the HTTP-status mapping (§2.5). A fault is a bare union arm carrying the reserved is_err tag,
recognized by honest-type's is_fault, never raised and never enveloped (§2). Pure assertions: data and
injected callables in, data out, no mocks.
"""

from honest_type import is_fault

import honest_auth as A
from honest_auth import (
    auth_fault,
    authenticate,
    authentication_honesty,
    empty_registry,
    fault_status,
    register_auth_provider,
    registered_provider,
    resolve_actor_deterministic,
    validate_provider,
)

NOTHING = A.NOTHING

# The recognizer-reject code authenticate stamps on a token that fails actor_recognizer, the code
# _expect_recognizer_reject keys on to tell a recognizer reject from a resolution fault (§2.2, §4.7).
_MALFORMED_CODE = "malformed_token"

# --- the synthetic provider ------------------------------------------------------------------------
# A provider is a record of callables (§2). The dev wire format is any string beginning "tok:"; a token
# that does not match is malformed and never reaches the resolver. The resolver maps four live tokens to
# an Actor or a resolution fault; a token it does not know resolves to an unauthenticated fault.

_ACTOR = {"user_id": "u1"}

_RESOLVE = {
    "tok:valid":   dict(_ACTOR),
    "tok:revoked": {"is_err": True, "category": "revoked", "code": "revoked", "message": "the token was revoked", "detail": {}},
    "tok:expired": {"is_err": True, "category": "expired", "code": "expired", "message": "the token has expired", "detail": {}},
    "tok:forged":  {"is_err": True, "category": "forged",  "code": "forged",  "message": "the token maps to no identity", "detail": {}},
}

# The token each class is generated as (§2.4). malformed and missing do not match the recognizer.
_TOKENS = {
    "valid":     "tok:valid",
    "revoked":   "tok:revoked",
    "expired":   "tok:expired",
    "malformed": "garbage",
    "missing":   "",
    "forged":    "tok:forged",
}


def _recognizer(token):
    return isinstance(token, str) and token.startswith("tok:")


def _resolver(token):
    return _RESOLVE.get(token, {"is_err": True, "category": "unauthenticated", "code": "unresolved", "message": "no identity", "detail": {}})


def _generator(cls, context):
    return _TOKENS[cls]


def _provider(**override):
    """A well-formed synthetic provider, with named fields overridable to build the malformed and
    dishonest variants the laws need."""
    base = {
        "name": "dev",
        "actor_recognizer": _recognizer,
        "resolve_actor": _resolver,
        "test_token_generator": _generator,
        "fault_mapping": {"unauthenticated": 401, "forbidden": 403, "conflict": 409},
    }
    base.update(override)
    return base


# --- laws ------------------------------------------------------------------------------------------


def _law_exports():
    bad = []
    # The seven .hd import entries are the public surface — exactly these, in __all__.
    import_entries = [
        "empty_registry", "register_auth_provider", "registered_provider", "authenticate",
        "fault_status", "authentication_honesty", "resolve_actor_deterministic",
    ]
    # Reached only by invokes or the dispatch table, so importable attributes but not exported.
    internal = ["auth_fault", "validate_provider", "_expect_actor", "_expect_unauthenticated", "_expect_recognizer_reject"]
    all_ = getattr(A, "__all__", None)
    if all_ is None:
        bad.append("honest_auth declares no __all__")
        return bad
    if sorted(all_) != sorted(import_entries):
        bad.append(f"__all__ must be exactly the seven import entries {sorted(import_entries)}: {sorted(all_)}")
    missing = [n for n in import_entries + internal if not hasattr(A, n)]
    if missing:
        bad.append(f"these functions are not importable: {missing}")
    return bad


def _law_auth_fault():
    bad = []
    f = auth_fault("unauthenticated", "already_registered", "a provider is already active", {"existing": "dev"})
    if f.get("is_err") is not True:
        bad.append(f"auth_fault must set is_err true, the reserved arm tag: {f}")
    if not is_fault(f):
        bad.append("auth_fault's result must be recognized by is_fault off its is_err tag")
    if (f.get("category"), f.get("code"), f.get("message"), f.get("detail")) != (
        "unauthenticated", "already_registered", "a provider is already active", {"existing": "dev"}
    ):
        bad.append(f"auth_fault must carry its parts unchanged: {f}")
    return bad


def _law_empty_registry():
    bad = []
    r = empty_registry()
    if r.get("provider") is not NOTHING:
        bad.append(f"empty_registry's provider field must be NOTHING: {r}")
    if is_fault(r):
        bad.append("an empty Registry must never be recognized as a fault")
    return bad


def _law_registered_provider():
    bad = []
    if registered_provider(empty_registry()) is not NOTHING:
        bad.append("registered_provider on an empty registry must be NOTHING")
    p = _provider()
    r = register_auth_provider(empty_registry(), p)
    if registered_provider(r) is not p:
        bad.append("registered_provider must return the active provider once one is registered")
    # No is_fault check on the absence: NOTHING is None, not a Fault dict, so it is outside is_fault's
    # domain (§12.1 keeps is_fault to dicts) and disjoint from the fault space by construction. The
    # absence is told apart by `is NOTHING`, already asserted above on the empty registry.
    return bad


def _law_validate_provider():
    bad = []
    p = _provider()
    if validate_provider(p) is not p:
        bad.append("a well-formed provider must be returned unchanged")
    # Each missing required field faults with invalid_provider naming the field.
    for field in ("name", "actor_recognizer", "resolve_actor", "test_token_generator", "fault_mapping"):
        broken = _provider()
        del broken[field]
        out = validate_provider(broken)
        if not is_fault(out):
            bad.append(f"a provider missing {field} must fault")
            continue
        if out.get("code") != "invalid_provider":
            bad.append(f"a malformed provider faults with code invalid_provider: {out.get('code')}")
        if field not in str(out.get("detail")):
            bad.append(f"the fault detail must name the missing field {field}: {out.get('detail')}")
    # A fault_mapping that dropped the required unauthenticated category is malformed (§2.5).
    out = validate_provider(_provider(fault_mapping={"forbidden": 403}))
    if not is_fault(out) or out.get("code") != "invalid_provider":
        bad.append(f"a fault_mapping without unauthenticated must fault invalid_provider: {out}")
    return bad


def _law_register_auth_provider():
    bad = []
    p = _provider()
    empty = empty_registry()
    r = register_auth_provider(empty, p)
    if is_fault(r):
        bad.append(f"registering into an empty registry must succeed: {r}")
    if r.get("provider") is not p:
        bad.append("a successful registration carries the provider")
    # Never mutates its argument.
    if empty.get("provider") is not NOTHING:
        bad.append("register_auth_provider must not mutate its registry argument")
    # Already registered.
    out = register_auth_provider(r, _provider(name="other"))
    if not is_fault(out) or out.get("code") != "already_registered":
        bad.append(f"registering a second provider must fault already_registered: {out}")
    # Malformed provider surfaces validate_provider's invalid_provider fault.
    out = register_auth_provider(empty_registry(), _provider(fault_mapping={"forbidden": 403}))
    if not is_fault(out) or out.get("code") != "invalid_provider":
        bad.append(f"registering a malformed provider must fault invalid_provider: {out}")
    return bad


def _law_authenticate():
    bad = []
    p = _provider()
    # A recognized, live token resolves to an Actor, returned unchanged.
    actor = authenticate(p, "tok:valid")
    if is_fault(actor) or actor != _ACTOR:
        bad.append(f"a valid token must resolve to its Actor: {actor}")
    # A token that fails the recognizer is rejected before resolve_actor, as a recognizer-reject fault.
    out = authenticate(p, "garbage")
    if not is_fault(out):
        bad.append(f"a malformed token must be rejected as a fault: {out}")
    if out.get("code") != _MALFORMED_CODE:
        bad.append(f"the recognizer reject must carry code {_MALFORMED_CODE}: {out.get('code')}")
    if out.get("category") != "unauthenticated":
        bad.append(f"the recognizer reject must carry category unauthenticated: {out.get('category')}")
    # A recognized token that the resolver fails returns the resolver's fault unchanged.
    out = authenticate(p, "tok:revoked")
    if not is_fault(out) or out.get("category") != "revoked":
        bad.append(f"a recognized token's resolution fault must be returned unchanged: {out}")
    return bad


def _law_fault_status():
    bad = []
    p = _provider()
    cases = {"unauthenticated": 401, "forbidden": 403, "conflict": 409}
    for category, status in cases.items():
        f = auth_fault(category, "x", "m", {})
        got = fault_status(p, f)
        if got != status:
            bad.append(f"fault_status for {category} must be {status}: {got}")
    # A provider that extends the mapping maps its own category.
    custom = _provider(fault_mapping={"unauthenticated": 401, "rate_limited": 429})
    got = fault_status(custom, auth_fault("rate_limited", "x", "m", {}))
    if got != 429:
        bad.append(f"a provider's custom category must map through fault_mapping: {got}")
    return bad


def _law_expect_checkers():
    bad = []
    fault = auth_fault("unauthenticated", "revoked", "m", {})
    reject = auth_fault("unauthenticated", _MALFORMED_CODE, "m", {})
    # _expect_actor: true only for an Actor.
    if A._expect_actor("valid", _ACTOR) is not True:
        bad.append("_expect_actor must pass an Actor")
    if A._expect_actor("valid", fault) is not False:
        bad.append("_expect_actor must fail a Fault")
    # _expect_unauthenticated: true only for a Fault.
    if A._expect_unauthenticated("revoked", fault) is not True:
        bad.append("_expect_unauthenticated must pass a Fault")
    if A._expect_unauthenticated("revoked", _ACTOR) is not False:
        bad.append("_expect_unauthenticated must fail an Actor")
    # _expect_recognizer_reject: true only for a recognizer-reject fault, by its code.
    if A._expect_recognizer_reject("malformed", reject) is not True:
        bad.append("_expect_recognizer_reject must pass a recognizer-reject fault")
    if A._expect_recognizer_reject("malformed", fault) is not False:
        bad.append("_expect_recognizer_reject must fail a resolution fault (wrong code)")
    if A._expect_recognizer_reject("malformed", _ACTOR) is not False:
        bad.append("_expect_recognizer_reject must fail an Actor")
    return bad


def _law_authentication_honesty():
    bad = []
    p = _provider()
    out = authentication_honesty(p, {})
    if is_fault(out):
        bad.append(f"an honest provider must pass the honesty verifier unchanged: {out}")
    if out is not p:
        bad.append("the honesty verifier returns the provider unchanged on success")
    # A provider whose resolver hands an Actor back for a revoked token is dishonest at that class.
    def _lying_resolver(token):
        if token == "tok:revoked":
            return dict(_ACTOR)
        return _resolver(token)

    liar = _provider(resolve_actor=_lying_resolver)
    out = authentication_honesty(liar, {})
    if not is_fault(out):
        bad.append("a dishonest provider must fail the honesty verifier")
    elif "revoked" not in str(out.get("detail")):
        bad.append(f"the honesty fault must name every wrong class: {out.get('detail')}")
    return bad


def _law_resolve_actor_deterministic():
    bad = []
    p = _provider()
    # Two Actors that match agree; two faults of the same category agree.
    if resolve_actor_deterministic(p, "tok:valid") is not True:
        bad.append("a deterministic resolver must agree on a valid token")
    if resolve_actor_deterministic(p, "tok:revoked") is not True:
        bad.append("two faults of the same category must agree")
    # A resolver that returns a different actor each call is not deterministic.
    seq = iter([{"user_id": "a"}, {"user_id": "b"}])

    def _flaky(token):
        return next(seq)

    if resolve_actor_deterministic(_provider(resolve_actor=_flaky), "tok:valid") is not False:
        bad.append("a non-deterministic resolver must be reported as not deterministic")
    return bad


_LAWS = {
    "exports": _law_exports,
    "auth_fault": _law_auth_fault,
    "empty_registry": _law_empty_registry,
    "registered_provider": _law_registered_provider,
    "validate_provider": _law_validate_provider,
    "register_auth_provider": _law_register_auth_provider,
    "authenticate": _law_authenticate,
    "fault_status": _law_fault_status,
    "expect_checkers": _law_expect_checkers,
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


if __name__ == "__main__":
    raise SystemExit(run())
