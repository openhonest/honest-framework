# scenario: run_mutation_check passes the original and detects its change
# inherits: hd=python/honest-test/honest-test.hd::run_mutation_check -> feature=specs/features/honest-test.feature::run_mutation_check passes the original and detects its change
"""Verify that run_mutation_check passes the original and detects its change."""


def probe_run_mutation_check_original():
    try:
        from honest_test.honesty import run_mutation_check
    except ImportError as exc:
        return [f"cannot import run_mutation_check: {exc}"]

    original = {"slot": {"count": 1}}
    received = []

    def link(argument):
        received.append(argument)
        argument["slot"]["count"] = 2
        return argument["slot"]["count"]

    got = run_mutation_check(link, original)
    if len(received) != 1 or received[0] is not original or original != {"slot": {"count": 2}}:
        return ["run_mutation_check did not call the link once with the mutable original"]
    expected = [("failure", "manifest_mutated", True, True)]
    actual = [
        (
            finding["kind"], finding["code"],
            "{'slot': {'count': 1}}" in finding["message"],
            "{'slot': {'count': 2}}" in finding["message"],
        )
        for finding in got
    ]
    if actual != expected:
        return [f"run_mutation_check returned {got!r}, expected a failure naming both manifests"]
    return []



def run():
    failures = probe_run_mutation_check_original()
    for failure in failures:
        print(f"FAIL probe_run_mutation_check_original: {failure}")
    return len(failures)
