"""Conformance fragment for the compute_expected_status scenario (honest-test.feature).

Scenario: compute_expected_status maps one token class to the HTTP status the auth
  check expects.
  Then it returns 401 for revoked, expired, missing and forged (an unauthenticated
  fault), 400 or the provider's preferred status for malformed (rejected at the
  recognizer), and the ok path for valid carries no error status.
  And the provider may override the default through fault_mapping.

Cases are data; one pure probe feeds them to the real function and returns a list of
failure strings (empty when every case holds). No classes, no mocks: it calls the real
honest_test.compute_expected_status.

This is its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.

GAP: the valid class is not encoded. The note and the scenario say valid "carries no
error status" but fix no concrete int for a function typed to return int. Asserting a
value here would be inventing it, so valid stays out of _CASES and is reported as a gap
owned by the feature file and the .hd.
"""

from honest_test import compute_expected_status

_CASES = [
    # Default mapping (empty fault_mapping): the four unauthenticated faults are 401.
    {"given": {"token_class": "revoked", "fault_mapping": {}}, "expect": 401},
    {"given": {"token_class": "expired", "fault_mapping": {}}, "expect": 401},
    {"given": {"token_class": "missing", "fault_mapping": {}}, "expect": 401},
    {"given": {"token_class": "forged", "fault_mapping": {}}, "expect": 401},
    # Default mapping: malformed is rejected at the recognizer, 400.
    {"given": {"token_class": "malformed", "fault_mapping": {}}, "expect": 400},
    # Override path: the provider's fault_mapping wins over the default.
    # malformed defaults to 400; the override forces 401.
    {"given": {"token_class": "malformed", "fault_mapping": {"malformed": 401}}, "expect": 401},
    # revoked defaults to 401; the override forces the provider's preferred status.
    {"given": {"token_class": "revoked", "fault_mapping": {"revoked": 403}}, "expect": 403},
]


def probe_compute_expected_status():
    """compute_expected_status returns 401 for the unauthenticated faults, 400 for malformed, and the provider's fault_mapping override when one is given."""
    bad = []
    for case in _CASES:
        got = compute_expected_status(**case["given"])
        if got != case["expect"]:
            bad.append(
                f"compute_expected_status({case['given']}) -> {got}, "
                f"expected {case['expect']}"
            )
    return bad


def run():
    bad = probe_compute_expected_status()
    for line in bad:
        print(line)
    print(f"probe_compute_expected_status: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
