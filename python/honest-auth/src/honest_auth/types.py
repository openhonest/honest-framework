"""The honest-auth data dictionary and its two foundations: the absence sentinel, and the single
place a fault is built (honest-auth-architecture.md §2, §3).

honest-auth owns three record shapes — the AuthProvider plugin contract, the Registry value, and the
Fault — and no class: each is a TypedDict, data with no behaviour attached (§2). A fault is a bare
union arm (value | Fault), recognized by honest-type's is_fault off the reserved is_err tag, never
raised and never wrapped in an ok/err envelope (§2). auth_fault is the one constructor that assembles
one, so is_err is set in exactly one place.
"""

from typing import Callable, TypedDict

# The empty tuple is the bounded absence a lookup yields when no provider is registered (§3.2). It
# carries no is_err tag, so honest-type's is_fault never recognizes it, keeping the absence disjoint
# from a Fault; and it is immutable, so a shared NOTHING can never be mutated into something else.
NOTHING = ()

# The code authenticate stamps on a token that fails actor_recognizer, before resolve_actor runs
# (§2.2, §2.4). _expect_recognizer_reject keys on it to tell a recognizer reject from a resolution
# fault, so the two live in one place rather than drifting between stamp site and check site (§4.7).
MALFORMED_CODE = "malformed_token"

# The five fields every AuthProvider must supply, checked by validate_provider before registration
# (§2, §9.1). Named once here so the contract and its check read the same list.
REQUIRED_FIELDS = ("name", "actor_recognizer", "resolve_actor", "test_token_generator", "fault_mapping")

# The fault category every provider's fault_mapping must retain, whatever custom categories it adds
# (§2.5). A mapping that drops it cannot answer the no-valid-identity case, so validate_provider
# rejects it.
REQUIRED_CATEGORIES = ("unauthenticated",)


class Fault(TypedDict):
    """An AuthFault — the failure an authentication function returns as a bare union arm (§2). is_err
    is the reserved boolean tag, always true, the mark is_fault reads to tell the fault arm from the
    value arm. category is one of the closed FaultCategory words. code is the specific reason. message
    is the human sentence. detail is the structured context."""

    is_err: bool
    category: str
    code: str
    message: str
    detail: dict


class AuthProvider(TypedDict):
    """The plugin contract every authentication implementation satisfies, a record of callables with
    no methods and no class (§2). honest-auth holds this record and composes its callables; it never
    constructs a provider, and only the provider's resolve_actor performs I/O, at the application's
    request boundary (§2.3)."""

    name: str
    actor_recognizer: Callable
    resolve_actor: Callable
    test_token_generator: Callable
    fault_mapping: dict


class Registry(TypedDict):
    """The authentication registry, a value threaded through the application rather than module state
    (§3). Exactly one provider is active per application instance, so it carries a single optional
    provider: an AuthProvider once one is registered, NOTHING before any is (§3, §3.2)."""

    provider: object


def auth_fault(category, code, message, detail) -> Fault:
    """Build one AuthFault record from its parts — the single place honest-auth assembles a fault
    (§2). It sets is_err true and returns the Fault, carried by the return as a bare union arm and
    recognized by is_fault, never raised and never wrapped in an envelope (§2). Pure: it reads no
    world."""
    return {"is_err": True, "category": category, "code": code, "message": message, "detail": detail}
