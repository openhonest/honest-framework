"""Conformance fragment for the test_css_isolation scenario (honest-test.feature).

Scenario: test_css_isolation reports css_namespace_collision when two components
  share a CSS class.
  Then it extracts each component's CSS classes from its template with
  extract_css_classes and returns a css_namespace_collision failure Finding naming
  the shared classes when the two sets intersect, because each component must
  namespace under its own BEM block. It returns the failure when they collide,
  empty when their class namespaces are disjoint. It reads no world and returns
  pure data (section 7.1).

Cases are data; one pure probe feeds them to the real honest_test.test_css_isolation
and returns a list of failure strings (empty when every case holds). No classes, no
mocks: each Component is a plain dict {name, template, routes} and the probe reads
the returned Finding's code, kind and message by value. A sibling agent writes
extract_css_classes; this probe calls only test_css_isolation.

A Component here is {"name": str, "template": "<html...>", "routes": []}. routes is
empty because route collision is test_route_isolation's scenario, not this one.
Templates use double-quoted class attributes, matching the extract_css_classes
fragment.

A Finding is a plain dict carrying "kind", "code", "message" and "location". The
scenario fixes the code (css_namespace_collision), the kind (failure), and that the
message names the shared classes; it does not fix the exact message text, so the
probe asserts each shared class name appears in the message, not an exact string.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import test_css_isolation


def _component(name, template):
    return {"name": name, "template": template, "routes": []}


_CASES = [
    # (a) single shared class: both templates use class="card" -> one collision
    # finding naming the shared class "card".
    {
        "given": {
            "component_a": _component("alpha", '<div class="card"></div>'),
            "component_b": _component("beta", '<section class="card"></section>'),
        },
        "expect_collision": True,
        "shared": {"card"},
    },
    # (b) disjoint, BEM-namespaced: "foo__title" vs "bar__title" never intersect
    # -> the explicit empty list.
    {
        "given": {
            "component_a": _component("foo", '<h1 class="foo__title"></h1>'),
            "component_b": _component("bar", '<h1 class="bar__title"></h1>'),
        },
        "expect_collision": False,
        "shared": set(),
    },
    # (c) more than one shared class: both use "card" and "btn" -> the finding
    # names the whole shared set.
    {
        "given": {
            "component_a": _component(
                "alpha", '<div class="card btn foo__only"></div>'
            ),
            "component_b": _component(
                "gamma", '<div class="card btn bar__only"></div>'
            ),
        },
        "expect_collision": True,
        "shared": {"card", "btn"},
    },
]


def probe_test_css_isolation():
    """test_css_isolation returns a css_namespace_collision failure Finding naming the shared CSS classes when two components' class sets intersect, and an empty list when their namespaces are disjoint."""
    bad = []
    for case in _CASES:
        given = case["given"]
        got = test_css_isolation(**given)
        if not case["expect_collision"]:
            if got != []:
                bad.append(
                    f"test_css_isolation({given}) -> {got}, expected [] "
                    f"(disjoint class namespaces must not collide)"
                )
            continue
        if len(got) != 1:
            bad.append(
                f"test_css_isolation({given}) -> {got}, expected exactly one "
                f"css_namespace_collision finding"
            )
            continue
        finding = got[0]
        if finding.get("code") != "css_namespace_collision":
            bad.append(
                f"test_css_isolation({given}) finding code -> "
                f"{finding.get('code')}, expected 'css_namespace_collision'"
            )
        if finding.get("kind") != "failure":
            bad.append(
                f"test_css_isolation({given}) finding kind -> "
                f"{finding.get('kind')}, expected 'failure'"
            )
        message = finding.get("message", "")
        for cls in case["shared"]:
            if cls not in message:
                bad.append(
                    f"test_css_isolation({given}) message {message!r} does not "
                    f"name shared class {cls!r}"
                )
    return bad


def run():
    bad = probe_test_css_isolation()
    for line in bad:
        print(line)
    print(f"probe_test_css_isolation: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
