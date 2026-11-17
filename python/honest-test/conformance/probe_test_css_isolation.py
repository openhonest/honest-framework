"""honest-test conformance: test_css_isolation.

test_css_isolation(component_a, component_b) -> list<Finding> extracts each component's
CSS classes from its template and returns a css_namespace_collision failure naming the
shared classes when the two sets intersect, because each component must namespace under
its own BEM block; the empty list when their class namespaces are disjoint
(honest-test-architecture.md section 7.1).

A pure check over two real Component records. This probe builds a clean pair (disjoint
classes) and a violating pair (one shared class) and asserts the findings. No classes, no
mocks; a Finding is recognized by its own shape — a dict carrying a "code" and a "kind" —
never raised.
"""

from honest_test import test_css_isolation


def _is_finding(value):
    return isinstance(value, dict) and "code" in value and "kind" in value


def _component(name, template):
    return {"name": name, "template": template, "routes": []}


def probe_test_css_isolation():
    bad = []

    # Clean: BEM blocks "card" and "panel" share no class name.
    card = _component("card", '<div class="card card__title">a</div>')
    panel = _component("panel", '<div class="panel panel__title">b</div>')
    clean = test_css_isolation(card, panel)
    if not isinstance(clean, list):
        bad.append(f"test_css_isolation should return a list, got {clean!r}")
    elif clean != []:
        bad.append(f"two components with disjoint classes should yield no findings, got {clean!r}")

    # Violating: both templates reference the class "shared".
    left = _component("left", '<div class="left shared">a</div>')
    right = _component("right", '<div class="right shared">b</div>')
    dirty = test_css_isolation(left, right)
    if not isinstance(dirty, list) or len(dirty) != 1:
        bad.append(f"one shared class should yield exactly one finding, got {dirty!r}")
    else:
        finding = dirty[0]
        if not _is_finding(finding):
            bad.append(f"the result should be a Finding carrying a code and a kind, got {finding!r}")
        else:
            if finding.get("code") != "css_namespace_collision":
                bad.append(f"the code should be css_namespace_collision, got {finding.get('code')!r}")
            if finding.get("kind") != "failure":
                bad.append(f"a CSS collision is a failure, got kind {finding.get('kind')!r}")
            message = finding.get("message", "")
            if "shared" not in message:
                bad.append(f"the message should name the shared class 'shared', got {message!r}")
            if "left" not in message or "right" not in message:
                bad.append(f"the message should name both components, got {message!r}")

    return bad


def run():
    messages = probe_test_css_isolation()
    for message in messages:
        print(f"FAIL HT-probe [test_css_isolation]: {message}")
    print(f"test_css_isolation: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
