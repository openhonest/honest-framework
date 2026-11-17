"""honest-test conformance: compute_expected_status maps a token class to its HTTP status.

Spec section 4.7 (class-to-outcome table), feature "compute_expected_status maps one token
class to its expected HTTP status", .hd compute_expected_status. It returns 401 for
revoked, expired, missing and forged (an unauthenticated fault), and 400 for malformed
(rejected at the recognizer) by default. The valid class takes the ok path and carries no
error status, so it is not asserted here. It reads no world and returns pure data.

The override through fault_mapping is left unasserted: the sources name the default
mapping but do not pin the key fault_mapping is indexed by for an override, so pinning one
here would encode a guess rather than the spec.
"""

from honest_test import compute_expected_status


def probe_compute_expected_status():
    bad = []

    for token_class in ("revoked", "expired", "missing", "forged"):
        got = compute_expected_status(token_class, {})
        if got != 401:
            bad.append(f"{token_class} is an unauthenticated fault and must map to 401, got {got!r}")

    malformed = compute_expected_status("malformed", {})
    if malformed != 400:
        bad.append(f"malformed is rejected at the recognizer and must map to 400 by default, got {malformed!r}")

    return bad


def run():
    messages = probe_compute_expected_status()
    for message in messages:
        print(f"FAIL HT-probe [compute_expected_status]: {message}")
    print(f"compute_expected_status: {'passed' if not messages else f'{len(messages)} failed'}")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
