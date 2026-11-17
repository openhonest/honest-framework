"""honest-test conformance: test_auth_honesty probes a provider with each token class.

Spec section 4.7, feature "test_auth_honesty probes a provider with each token class", .hd
test_auth_honesty. For each of the six token classes it generates a token with the
provider's test_token_generator and asserts the outcome, returning an auth_honesty failure
when the provider accepts a malformed token at the recognizer, rejects a valid one, or
does not fault correctly for a class. A malformed token must be rejected at the
actor_recognizer before resolve_actor; a valid token must resolve to ok(actor); every
other class must fault with the expected HTTP status.

No classes, no mocks. The provider is a real AuthProvider value (honest-auth's five-field
shape) built here with real pure functions, never reached from a registry. One provider
validates its boundary soundly across all six classes; one accepts a malformed token at
the recognizer. resolve_actor returns honest-type's ok/err Result; a fault carries a
"category" the fault_mapping maps to a status. A Finding carries a "code" and a "kind".
"""

from honest_type import err, fault, ok

from honest_test import test_auth_honesty


def _codes(findings):
    return [f.get("code") for f in findings if isinstance(f, dict)]


def _generate(class_name):
    """The provider's test token for a class — a string encoding the class it stands for."""
    return f"token:{class_name}"


def _sound_recognizer(token):
    """Accepts a well-formed token; rejects the malformed one before resolve_actor."""
    return token != "token:malformed"


def _sound_resolve(token):
    """Resolves the valid token to ok(actor); faults every other class as unauthenticated."""
    if token == "token:valid":
        return ok({"actor": "alice"})
    return err(fault("unauthenticated", f"rejected {token}", "unauthenticated", [], {}))


def _accepts_malformed_recognizer(token):
    """Accepts every token, malformed included — the dishonest boundary."""
    return True


_SOUND_PROVIDER = {
    "name": "sound",
    "actor_recognizer": _sound_recognizer,
    "resolve_actor": _sound_resolve,
    "test_token_generator": _generate,
    "fault_mapping": {"unauthenticated": 401},
}

_BROKEN_PROVIDER = {
    "name": "accepts-malformed",
    "actor_recognizer": _accepts_malformed_recognizer,
    "resolve_actor": _sound_resolve,
    "test_token_generator": _generate,
    "fault_mapping": {"unauthenticated": 401},
}


def probe_test_auth_honesty():
    bad = []

    sound = test_auth_honesty(_SOUND_PROVIDER)
    if sound != []:
        bad.append(f"a provider with sound boundary validation should yield no finding, got {sound!r}")

    broken = test_auth_honesty(_BROKEN_PROVIDER)
    if not broken or set(_codes(broken)) != {"auth_honesty"}:
        bad.append(
            f"a provider that accepts a malformed token at the recognizer should yield an "
            f"auth_honesty failure, got {broken!r}"
        )
    elif {f.get("kind") for f in broken} != {"failure"}:
        bad.append(f"an auth_honesty finding must be graded a failure, got {broken!r}")

    return bad


def run():
    messages = probe_test_auth_honesty()
    for message in messages:
        print(f"FAIL HT-probe [test_auth_honesty]: {message}")
    print(f"test_auth_honesty: {'passed' if not messages else f'{len(messages)} failed'}")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
