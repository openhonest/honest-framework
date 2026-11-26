# scenario: run_auth_honesty_check propagates unexpected callback errors
# inherits: hd=python/honest-test/honest-test.hd::run_auth_honesty_check -> feature=specs/features/honest-test.feature::run_auth_honesty_check propagates unexpected callback errors

from honest_type import ok

from honest_test.honesty import run_auth_honesty_check


def probe_run_auth_honesty_check_exception():
    error = RuntimeError("provider recognizer failed")

    def generate(token_class):
        return f"token:{token_class}"

    def recognize(token):
        raise error

    def resolve(token):
        return ok({"actor": token})

    provider = {
        "name": "broken-callback",
        "test_token_generator": generate,
        "actor_recognizer": recognize,
        "resolve_actor": resolve,
        "fault_mapping": {"unauthenticated": 401},
    }
    try:
        run_auth_honesty_check(provider)
    except RuntimeError as raised:
        return [] if raised is error else ["the original callback error was replaced"]
    return ["the recognizer's RuntimeError did not propagate"]


def run():
    failures = probe_run_auth_honesty_check_exception()
    for failure in failures:
        print(f"FAIL run_auth_honesty_check propagates unexpected callback errors: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())
