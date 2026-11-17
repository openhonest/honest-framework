"""The executable authentication-honesty verifier and the determinism check
(honest-auth-architecture.md §4.4, §4.7). A provider's honesty is checked, not asserted: the verifier
folds every token class through authenticate and the per-class outcome table, and reports the classes
whose outcome was wrong. Pure over the provider's injected generator and resolver — deterministic and
mock-free.
"""

from honest_type import is_fault

from honest_auth._util import _pick
from honest_auth.authenticate import authenticate
from honest_auth.types import MALFORMED_CODE, auth_fault


def _expect_actor(cls, result):
    """The outcome checker for the valid token class (§4.7). True when result is an Actor and not a
    fault — the valid class must resolve to an actor — recognizing a Fault by its is_err tag through
    is_fault. Reached through the class_outcome table; reads no world and returns no fault."""
    return not is_fault(result)


def _expect_unauthenticated(cls, result):
    """The outcome checker for the revoked, expired, missing and forged token classes (§4.7). True
    when result is a Fault — the class must fail as unauthenticated, no valid identity — recognizing
    the fault by its is_err tag through is_fault. Reached through the class_outcome table; reads no
    world and returns no fault."""
    return is_fault(result)


def _expect_recognizer_reject(cls, result):
    """The outcome checker for the malformed token class (§4.7). True when result is a Fault produced
    by the recognizer before resolve_actor ran — authenticate's recognizer-reject fault — told from a
    resolution fault by its code, so the check confirms the token was rejected at actor_recognizer and
    not resolved (§2.2, §4.7). Reached through the class_outcome table; reads no world and returns no
    fault."""
    return is_fault(result) and result.get("code") == MALFORMED_CODE


# The token-class-to-expected-outcome table the honesty verifier folds each class through (§4.7). Its
# keys are exactly the six token classes; its values are the three outcome checkers. Folding its
# .items() makes the six classes and their required outcomes a declared, countable value, so a
# verifier that silently checked only one class could not ship green.
_CLASS_OUTCOME = {
    "valid": _expect_actor,
    "revoked": _expect_unauthenticated,
    "expired": _expect_unauthenticated,
    "malformed": _expect_recognizer_reject,
    "missing": _expect_unauthenticated,
    "forged": _expect_unauthenticated,
}


def authentication_honesty(provider, context):
    """The executable authentication-honesty verifier (§4.7). It folds over every token class in the
    class_outcome table and, for each, generates a token with the provider's injected
    test_token_generator against context, sends it through authenticate, and selects the right outcome
    checker. It returns the provider unchanged when every class's outcome is right, or an auth_fault
    whose detail lists every class whose outcome was wrong. Pure over the injected generator and
    resolver, deterministic and mock-free."""

    def _class_wrong(pair):
        # Generate a token for one class, send it through authenticate, and report whether its
        # outcome was wrong (§4.7). Wrong is the negation of the class's own checker. The token
        # generator is called as an injected record field.
        cls, checker = pair
        token = provider["test_token_generator"](cls, context)
        result = authenticate(provider, token)
        return not checker(cls, result)

    wrong = list(map(lambda pair: pair[0], filter(_class_wrong, _CLASS_OUTCOME.items())))
    return _pick(
        not wrong,
        lambda: provider,
        lambda: auth_fault(
            "conflict",
            "dishonest_provider",
            f"the provider's authentication is dishonest for these token classes: {wrong}",
            {"wrong_classes": wrong},
        ),
    )


def resolve_actor_deterministic(provider, token):
    """Resolve the same token twice under the same backing state and report whether the two results
    agree (§4.4, §4.7). It calls the injected resolve_actor twice and compares their determinism keys
    — two Actors that match, or two faults of the same category — returning true when they agree and
    false when they differ. Pure over the injected resolver; it reads no world of its own and
    propagates no honest-auth fault."""

    def _determinism_key(result):
        # Reduce a result to the value two calls must agree on (§4.4): a fault's category, or an
        # actor itself. Two faults agree when their categories match; two actors agree when they are
        # equal; a fault and an actor never agree, because their keys differ in the first position.
        return _pick(
            is_fault(result),
            lambda: ("fault", result.get("category")),
            lambda: ("actor", result),
        )

    first = provider["resolve_actor"](token)
    second = provider["resolve_actor"](token)
    return _determinism_key(first) == _determinism_key(second)
