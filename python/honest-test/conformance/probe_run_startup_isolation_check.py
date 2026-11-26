# scenario: run_startup_isolation_check loads components in reverse then forward order
# inherits: hd=python/honest-test/honest-test.hd::run_startup_isolation_check -> feature=specs/features/honest-test.feature::run_startup_isolation_check loads components in reverse then forward order

from honest_test.persist_components import run_startup_isolation_check


def probe_run_startup_isolation_check():
    components = [
        {"name": "trigger", "template": "", "routes": []},
        {"name": "dependent_a", "template": "", "routes": []},
        {"name": "dependent_b", "template": "", "routes": []},
    ]
    calls = []

    def load_component(component):
        name = component["name"]
        fail = name == "trigger" or "trigger" in calls
        calls.append(name)
        if fail:
            raise RuntimeError(f"{name} failed to load")

    findings = run_startup_isolation_check(components, load_component)
    expected_calls = ["dependent_b", "dependent_a", "trigger", "trigger", "dependent_a", "dependent_b"]
    if calls != expected_calls:
        return [f"load order was {calls!r}, expected {expected_calls!r}"]
    classifications = [(item["kind"], item["code"]) for item in findings]
    expected = [("failure", "startup_cascade"), ("failure", "startup_cascade")]
    if classifications != expected:
        return [f"got {classifications!r}, expected {expected!r}"]
    messages = [item["message"] for item in findings]
    if not all(name in message and "trigger" in message for name, message in zip(("dependent_a", "dependent_b"), messages)):
        return [f"cascade findings were not in original component order: {messages!r}"]
    return []


def run():
    failures = probe_run_startup_isolation_check()
    for failure in failures:
        print(f"FAIL run_startup_isolation_check loads components in reverse then forward order: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())
