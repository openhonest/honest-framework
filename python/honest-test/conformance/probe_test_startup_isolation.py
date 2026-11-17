"""honest-test conformance: test_startup_isolation.

test_startup_isolation(components, load_component) -> list<Finding> returns a
startup_cascade failure when one component failing to load causes another to fail to load,
the empty list when each component's load failure is isolated, because when one component
fails every other must still load (honest-test-architecture.md section 7.3).

load_component is the injected loader driving the genuine load; the effect of loading
belongs to it and honest-test only observes which loads then fail. This probe builds the
loader itself as a real pure function closed over local state: a clean loader whose one
failure is isolated, and a violating loader where loading one component poisons another.
No classes, no mocks; a Finding is recognized by its own shape — a dict carrying a "code"
and a "kind" — never raised.
"""

from honest_test import test_startup_isolation


def _is_finding(value):
    return isinstance(value, dict) and "code" in value and "kind" in value


def _component(name):
    return {"name": name, "template": "", "routes": []}


def probe_test_startup_isolation():
    bad = []
    broken = _component("broken")
    healthy = _component("healthy")

    # Clean: the loader fails only for "broken"; every other component loads regardless.
    def load_isolated(component):
        if component["name"] == "broken":
            raise RuntimeError("broken fails to load on its own")
        return component

    clean = test_startup_isolation([broken, healthy], load_isolated)
    if not isinstance(clean, list):
        bad.append(f"test_startup_isolation should return a list, got {clean!r}")
    elif clean != []:
        bad.append(f"an isolated load failure should yield no findings, got {clean!r}")

    # Violating: loading "trigger" poisons shared state so "dependent" then fails to load,
    # which is a real cascade — the dependent cannot load once the trigger has failed.
    trigger = _component("trigger")
    dependent = _component("dependent")
    poisoned = {"flag": False}

    def load_cascading(component):
        if component["name"] == "trigger":
            poisoned["flag"] = True
            raise RuntimeError("trigger fails to load")
        if component["name"] == "dependent" and poisoned["flag"]:
            raise RuntimeError("dependent cannot load after trigger failed")
        return component

    dirty = test_startup_isolation([trigger, dependent], load_cascading)
    if not isinstance(dirty, list) or len(dirty) < 1:
        bad.append(f"a cascading load failure should yield at least one finding, got {dirty!r}")
    else:
        for finding in dirty:
            if not _is_finding(finding):
                bad.append(f"each result should be a Finding carrying a code and a kind, got {finding!r}")
                continue
            if finding.get("code") != "startup_cascade":
                bad.append(f"the code should be startup_cascade, got {finding.get('code')!r}")
            if finding.get("kind") != "failure":
                bad.append(f"a startup cascade is a failure, got kind {finding.get('kind')!r}")
        joined = " ".join(f.get("message", "") for f in dirty if _is_finding(f))
        if "trigger" not in joined or "dependent" not in joined:
            bad.append(f"a cascade message should name the failing and the cascaded component, got {joined!r}")

    return bad


def run():
    messages = probe_test_startup_isolation()
    for message in messages:
        print(f"FAIL HT-probe [test_startup_isolation]: {message}")
    print(f"test_startup_isolation: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
