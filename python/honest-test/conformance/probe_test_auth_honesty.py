"""Conformance fragment for the test_auth_honesty scenario (honest-test.feature ~line 233).

Scenario: test_auth_honesty probes each token class and reports auth_honesty on
wrong behaviour.
  Then for each of the six token classes it generates a token with the provider's
  test_token_generator and asserts the provider's outcome: a malformed token must
  be rejected at the actor_recognizer before resolve_actor, a valid token must
  resolve to ok(actor), and every other class must fault with the expected HTTP
  status compute_expected_status derives.
  And it returns an auth_honesty failure Finding when the provider accepts a
  malformed token, rejects a valid one, or does not fault correctly for a class.
  And it returns one failure per class that behaved wrongly, empty when the
  provider's boundary validation is sound, performing no I/O of its own.

Cases are data; one pure probe feeds them to the real honest_test.test_auth_honesty
and returns a list of failure strings (empty when every case holds). No mocks: the
injected provider is a record of real pure functions matching the shape honest-auth's
dev_auth_provider builds (actor_recognizer, resolve_actor, test_token_generator,
fault_mapping), with Result values built by honest-type's real ok/err/fault. These
are real functions used as test input, not stand-ins.

Its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

from honest_type import err, fault, ok

from honest_test import test_auth_honesty

# The six token-class tokens the generator hands back. The malformed token is the
# one the recognizer must reject before resolve_actor; the others reach resolve_actor.
_TOKENS = {
    "valid": "VALID",
    "revoked": "REVOKED",
    "expired": "EXPIRED",
    "malformed": "MALFORMED",
    "missing": "MISSING",
    "forged": "FORGED",
}


def _token_generator(class_name, context):
    """The provider's test_token_generator: one distinct token per class (section 2.4)."""
    return _TOKENS[class_name]


# ---- an honest provider: sound boundary validation, so no failure on any class ----

def _honest_recognizer(token):
    """Rejects the malformed token, accepts every other wire-format token."""
    return token != "MALFORMED"


def _honest_resolve(token):
    """A valid token resolves to ok(actor); every other class faults unauthenticated (401)."""
    if token == "VALID":
        return ok({"id": "alice", "attributes": {}})
    return err(fault("unauthenticated", "not authenticated", "unauthenticated", [], {}))


_HONEST_PROVIDER = {
    "name": "honest-probe",
    "actor_recognizer": _honest_recognizer,
    "resolve_actor": _honest_resolve,
    "test_token_generator": _token_generator,
    "fault_mapping": {},
}


# ---- a dishonest provider wrong on exactly three classes ----
# 1. accepts the malformed token at the recognizer (malformed),
# 2. rejects a valid token (valid),
# 3. faults expired as forbidden (403) instead of unauthenticated (401) (expired).
# revoked, missing and forged stay correct, so exactly three classes behave wrongly.

def _dishonest_recognizer(token):
    """Accepts everything, including the malformed token — a wrong boundary."""
    return True


def _dishonest_resolve(token):
    """Rejects the valid token, mis-categorises the expired token, resolves the rest correctly."""
    if token == "VALID":
        return err(fault("unauthenticated", "wrongly rejected a valid token", "unauthenticated", [], {}))
    if token == "EXPIRED":
        return err(fault("forbidden", "wrong category for expired", "forbidden", [], {}))
    return err(fault("unauthenticated", "not authenticated", "unauthenticated", [], {}))


_DISHONEST_PROVIDER = {
    "name": "dishonest-probe",
    "actor_recognizer": _dishonest_recognizer,
    "resolve_actor": _dishonest_resolve,
    "test_token_generator": _token_generator,
    "fault_mapping": {},
}


_CASES = [
    # The honest provider's boundary validation is sound, so the check returns [].
    {
        "name": "honest provider",
        "provider": _HONEST_PROVIDER,
        "expect_failures": 0,
        "expect_empty": True,
    },
    # The dishonest provider behaves wrongly for malformed, valid and expired:
    # exactly three auth_honesty failures, one per wrong class. A stub returning []
    # fails this literal, non-trivial case.
    {
        "name": "dishonest provider (malformed, valid, expired wrong)",
        "provider": _DISHONEST_PROVIDER,
        "expect_failures": 3,
        "expect_empty": False,
    },
]


def probe_test_auth_honesty():
    """test_auth_honesty returns one auth_honesty failure per class the provider mishandles, and [] when the provider's boundary validation is sound."""
    bad = []
    for case in _CASES:
        got = test_auth_honesty(case["provider"])

        if case["expect_empty"]:
            if got != []:
                bad.append(
                    f"test_auth_honesty({case['name']}) -> {got}, expected []"
                )
            continue

        for finding in got:
            if finding["code"] != "auth_honesty":
                bad.append(
                    f"test_auth_honesty({case['name']}) emitted code "
                    f"{finding['code']!r}, expected 'auth_honesty'"
                )
            if finding["kind"] != "failure":
                bad.append(
                    f"test_auth_honesty({case['name']}) emitted kind "
                    f"{finding['kind']!r}, expected 'failure'"
                )

        auth_failures = [
            f
            for f in got
            if f.get("code") == "auth_honesty" and f.get("kind") == "failure"
        ]
        if len(auth_failures) != case["expect_failures"]:
            bad.append(
                f"test_auth_honesty({case['name']}) produced "
                f"{len(auth_failures)} auth_honesty failures, "
                f"expected {case['expect_failures']}"
            )
    return bad


def run():
    bad = probe_test_auth_honesty()
    for line in bad:
        print(line)
    print(f"probe_test_auth_honesty: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
