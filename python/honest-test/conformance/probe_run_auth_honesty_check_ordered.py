# scenario: run_auth_honesty_check probes token classes in order and resolves only eligible tokens
# inherits: hd=python/honest-test/honest-test.hd::run_auth_honesty_check -> feature=specs/features/honest-test.feature::run_auth_honesty_check probes token classes in order and resolves only eligible tokens

from honest_type import err, fault, ok

from honest_test.honesty import run_auth_honesty_check


def probe_run_auth_honesty_check_ordered():
    calls = []

    def generate(token_class):
        calls.append(("generate", token_class))
        return f"token:{token_class}"

    def recognize(token):
        calls.append(("recognize", token))
        return token != "token:missing"

    def resolve(token):
        calls.append(("resolve", token))
        if token == "token:valid":
            return ok({"actor": "alice"})
        return err(fault("rejected", "token rejected", "unauthenticated", [], {}))

    provider = {
        "name": "observed",
        "test_token_generator": generate,
        "actor_recognizer": recognize,
        "resolve_actor": resolve,
        "fault_mapping": {"unauthenticated": 401},
    }
    findings = run_auth_honesty_check(provider)
    expected_calls = [
        ("generate", "valid"), ("recognize", "token:valid"), ("resolve", "token:valid"),
        ("generate", "malformed"), ("recognize", "token:malformed"),
        ("generate", "revoked"), ("recognize", "token:revoked"), ("resolve", "token:revoked"),
        ("generate", "expired"), ("recognize", "token:expired"), ("resolve", "token:expired"),
        ("generate", "missing"), ("recognize", "token:missing"),
        ("generate", "forged"), ("recognize", "token:forged"), ("resolve", "token:forged"),
    ]
    if calls != expected_calls:
        return [f"got calls {calls!r}, expected {expected_calls!r}"]
    classifications = [(item["kind"], item["code"]) for item in findings]
    expected = [("failure", "auth_honesty"), ("failure", "auth_honesty")]
    if classifications != expected:
        return [f"got {classifications!r}, expected {expected!r}"]
    messages = [item["message"] for item in findings]
    if "malformed" not in messages[0] or "missing" not in messages[1]:
        return [f"expected failed malformed then missing observations, got {messages!r}"]
    return []


def run():
    failures = probe_run_auth_honesty_check_ordered()
    for failure in failures:
        print(f"FAIL run_auth_honesty_check probes token classes in order and resolves only eligible tokens: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())
