# scenario: auth_probe_findings accepts sound observations for each mode
# inherits: hd=python/honest-test/honest-test.hd::auth_probe_findings -> feature=specs/features/honest-test.feature::auth_probe_findings accepts sound observations for each mode

from honest_type import err, fault, ok

from honest_test.honesty import auth_probe_findings


def probe_auth_probe_findings_sound():
    fault_mapping = {"unauthenticated": 401}
    cases = (
        ("malformed", "malformed", False, None, 400),
        ("valid", "valid", True, ok({"actor": "alice"}), 401),
        ("revoked", "faulting", True, err(fault("revoked", "token revoked", "unauthenticated", [], {})), 401),
    )
    failures = []
    for token_class, mode, accepted, resolved, expected in cases:
        findings = auth_probe_findings(token_class, mode, accepted, resolved, fault_mapping, expected)
        if findings != []:
            failures.append(f"{token_class}: got {findings!r}, expected no findings")
    return failures


def run():
    failures = probe_auth_probe_findings_sound()
    for failure in failures:
        print(f"FAIL auth_probe_findings accepts sound observations for each mode: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())
