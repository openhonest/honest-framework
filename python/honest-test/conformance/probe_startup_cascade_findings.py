# scenario: startup_cascade_findings reports forward failures that passed in reverse
# inherits: hd=python/honest-test/honest-test.hd::startup_cascade_findings -> feature=specs/features/honest-test.feature::startup_cascade_findings reports forward failures that passed in reverse

from honest_test.persist_components import startup_cascade_findings


def probe_startup_cascade_findings():
    names = ["trigger", "second", "dependent", "healthy", "unobserved"]
    reverse = {"trigger": True, "second": False, "dependent": True, "healthy": True}
    forward = [
        {"name": "trigger", "loaded": False},
        {"name": "second", "loaded": False},
        {"name": "dependent", "loaded": False},
        {"name": "healthy", "loaded": True},
        {"name": "unobserved", "loaded": False},
    ]
    findings = startup_cascade_findings(names, reverse, forward)
    classifications = [(item["kind"], item["code"]) for item in findings]
    expected = [("failure", "startup_cascade"), ("failure", "startup_cascade")]
    if classifications != expected:
        return [f"got {classifications!r}, expected {expected!r}"]
    first, second = [item["message"] for item in findings]
    if "trigger" not in first or "an earlier component" not in first:
        return [f"expected the first finding to name trigger and its unknown predecessor, got {first!r}"]
    if "dependent" not in second or "trigger" not in second:
        return [f"expected the second finding to name dependent and first failed trigger, got {second!r}"]
    return []


def run():
    failures = probe_startup_cascade_findings()
    for failure in failures:
        print(f"FAIL startup_cascade_findings reports forward failures that passed in reverse: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())
