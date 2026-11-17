"""honest-test conformance: test_route_isolation.

test_route_isolation(components) -> list<Finding> accumulates every component's route
paths and returns a route_collision failure naming both components when a path is defined
twice; one failure per collided path, the empty list when every route path is unique
(honest-test-architecture.md section 7.2).

A pure check over a list of real Component records. This probe builds a clean set (unique
paths) and a violating set (one path defined by two components) and asserts the findings.
No classes, no mocks; a Finding is recognized by its own shape — a dict carrying a "code"
and a "kind" — never raised.
"""

from honest_test import test_route_isolation


def _is_finding(value):
    return isinstance(value, dict) and "code" in value and "kind" in value


def _component(name, paths):
    return {"name": name, "template": "", "routes": [{"path": path} for path in paths]}


def probe_test_route_isolation():
    bad = []

    # Clean: every route path is unique across components.
    clean = test_route_isolation([
        _component("home", ["/"]),
        _component("blog", ["/blog", "/blog/new"]),
        _component("about", ["/about"]),
    ])
    if not isinstance(clean, list):
        bad.append(f"test_route_isolation should return a list, got {clean!r}")
    elif clean != []:
        bad.append(f"unique route paths should yield no findings, got {clean!r}")

    # Violating: two components both define "/dash".
    dirty = test_route_isolation([
        _component("alpha", ["/dash", "/alpha"]),
        _component("beta", ["/dash"]),
    ])
    if not isinstance(dirty, list) or len(dirty) != 1:
        bad.append(f"one path defined twice should yield exactly one finding, got {dirty!r}")
    else:
        finding = dirty[0]
        if not _is_finding(finding):
            bad.append(f"the result should be a Finding carrying a code and a kind, got {finding!r}")
        else:
            if finding.get("code") != "route_collision":
                bad.append(f"the code should be route_collision, got {finding.get('code')!r}")
            if finding.get("kind") != "failure":
                bad.append(f"a route collision is a failure, got kind {finding.get('kind')!r}")
            message = finding.get("message", "")
            if "/dash" not in message:
                bad.append(f"the message should name the collided path '/dash', got {message!r}")
            if "alpha" not in message or "beta" not in message:
                bad.append(f"the message should name both components, got {message!r}")

    return bad


def run():
    messages = probe_test_route_isolation()
    for message in messages:
        print(f"FAIL HT-probe [test_route_isolation]: {message}")
    print(f"test_route_isolation: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
