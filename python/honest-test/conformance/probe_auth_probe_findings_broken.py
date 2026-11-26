# scenario: auth_probe_findings reports observations that violate the mode contract
# inherits: hd=python/honest-test/honest-test.hd::auth_probe_findings -> feature=specs/features/honest-test.feature::auth_probe_findings reports observations that violate the mode contract

from honest_type import err, fault, ok

from honest_test.honesty import auth_probe_findings


def probe_auth_probe_findings_broken():
    fault_mapping = {"unauthenticated": 401}
    accepted_actor = ok({"actor": "alice"})
    rejection = err(fault("rejected", "token rejected", "unauthenticated", [], {}))
    cases = (
        ("malformed", "malformed", True, None, 400),
        ("valid", "valid", False, accepted_actor, 401),
        ("valid", "valid", True, rejection, 401),
        ("revoked", "faulting", False, rejection, 401),
        ("expired", "faulting", True, accepted_actor, 401),
        ("forged", "faulting", True, rejection, 403),
    )
    failures = []
    for token_class, mode, accepted, resolved, expected in cases:
        findings = auth_probe_findings(token_class, mode, accepted, resolved, fault_mapping, expected)
        classifications = [(item["kind"], item["code"]) for item in findings]
        if classifications != [("failure", "auth_honesty")]:
            failures.append(f"{token_class}: expected one auth_honesty failure, got {findings!r}")
        elif token_class not in findings[0]["message"]:
            failures.append(f"{token_class}: finding did not identify its token class: {findings[0]!r}")
    return failures


def run():
    failures = probe_auth_probe_findings_broken()
    for failure in failures:
        print(f"FAIL auth_probe_findings reports observations that violate the mode contract: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())
