# scenario: run_purity_check uses a fresh copy for each call
# inherits: hd=python/honest-test/honest-test.hd::run_purity_check -> feature=specs/features/honest-test.feature::run_purity_check uses a fresh copy for each call
"""Verify that run_purity_check uses a fresh copy for each call."""


def probe_run_purity_check_fresh_copies():
    try:
        from honest_test.honesty import run_purity_check
    except ImportError as exc:
        return [f"cannot import run_purity_check: {exc}"]

    original = {"slot": {"count": 1}}
    received = []
    starting_counts = []

    def link(argument):
        received.append(argument)
        starting_counts.append(argument["slot"]["count"])
        argument["slot"]["count"] += 1
        return argument["slot"]["count"]

    got = run_purity_check(link, original)
    if len(received) != 2 or starting_counts != [1, 1] or original != {"slot": {"count": 1}}:
        return [f"run_purity_check did not perform two isolated copies: {starting_counts!r}, {original!r}"]
    first, second = received
    if first is second or first is original or second is original or first["slot"] is second["slot"]:
        return ["run_purity_check reused a manifest or nested slot"]
    if got != []:
        return [f"run_purity_check returned {got!r} for two equal answers"]
    return []



def run():
    failures = probe_run_purity_check_fresh_copies()
    for failure in failures:
        print(f"FAIL probe_run_purity_check_fresh_copies: {failure}")
    return len(failures)
