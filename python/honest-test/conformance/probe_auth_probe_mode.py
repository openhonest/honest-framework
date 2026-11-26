# scenario: auth_probe_mode selects the mode for each token class
# inherits: hd=python/honest-test/honest-test.hd::auth_probe_mode -> feature=specs/features/honest-test.feature::auth_probe_mode selects the mode for each token class

from honest_test.honesty import auth_probe_mode


def probe_auth_probe_mode():
    cases = (
        ("valid", "valid"),
        ("malformed", "malformed"),
        ("revoked", "faulting"),
        ("expired", "faulting"),
        ("missing", "faulting"),
        ("forged", "faulting"),
    )
    failures = []
    for token_class, expected in cases:
        actual = auth_probe_mode(token_class)
        if actual != expected:
            failures.append(f"{token_class}: got {actual!r}, expected {expected!r}")
    return failures


def run():
    failures = probe_auth_probe_mode()
    for failure in failures:
        print(f"FAIL auth_probe_mode selects the mode for each token class: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())
