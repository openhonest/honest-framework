# scenario: run_idempotency_check uses a fresh deep copy for each call
# inherits: hd=python/honest-test/honest-test.hd::run_idempotency_check -> feature=specs/features/honest-test.feature::run_idempotency_check uses a fresh deep copy for each call
"""Verify that run_idempotency_check uses a fresh deep copy for each call."""


def probe_run_idempotency_check_fresh_copies():
    try:
        from honest_test.honesty import run_idempotency_check
    except ImportError as exc:
        return [f"cannot import run_idempotency_check: {exc}"]

    original = {"slot": {"count": 1}}
    received = []
    starting_counts = []

    def chain(argument):
        received.append(argument)
        starting_counts.append(argument["slot"]["count"])
        argument["slot"]["count"] += len(received)
        return argument["slot"]["count"]

    got = run_idempotency_check(chain, original)
    if len(received) != 2 or starting_counts != [1, 1] or original != {"slot": {"count": 1}}:
        return [f"run_idempotency_check did not perform two isolated copies: {starting_counts!r}, {original!r}"]
    first, second = received
    if first is second or first is original or second is original or first["slot"] is second["slot"]:
        return ["run_idempotency_check reused a manifest or nested slot"]
    actual = [(finding["kind"], finding["code"]) for finding in got]
    expected = [("failure", "not_idempotent")]
    if actual != expected:
        return [f"run_idempotency_check returned {actual!r}, expected {expected!r}"]
    return []



def run():
    failures = probe_run_idempotency_check_fresh_copies()
    for failure in failures:
        print(f"FAIL probe_run_idempotency_check_fresh_copies: {failure}")
    return len(failures)
