"""Conformance fragment for the test_route_isolation scenario (honest-test.feature ~line 345).

Scenario: test_route_isolation reports route_collision when two components define the same path.
  Given components: list of Component
  When test_route_isolation is called
  Then it accumulates every component's route paths and returns a route_collision
  failure Finding naming both components when a path is defined twice.
  And it returns one failure per collided path, empty when every route path is unique.
  And it reads no world and returns pure data.

Cases are data; one pure probe feeds them to the real honest_test.test_route_isolation
and returns a list of failure strings (empty when every case holds). No classes, no mocks:
the probe builds plain Component dicts and asserts on the returned Finding records' code
("route_collision") and kind ("failure"), on the count of findings, and on both colliding
component names appearing in the failure message.

Its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import test_route_isolation


def _component(name, paths):
    """A Component dict with an empty template and one ComponentRoute per path."""
    return {"name": name, "template": "", "routes": [{"path": p} for p in paths]}


_CASES = [
    # (a) Two components define the same path "/dashboard" -> exactly one
    # route_collision failure, and it names both components.
    {
        "given": [
            _component("alpha", ["/dashboard"]),
            _component("beta", ["/dashboard"]),
        ],
        "expect_count": 1,
        "expect_names": {"alpha", "beta"},
    },
    # (b) Every route path is distinct across every component -> empty list.
    {
        "given": [
            _component("alpha", ["/dashboard", "/alpha"]),
            _component("beta", ["/beta", "/settings"]),
            _component("gamma", ["/gamma"]),
        ],
        "expect_count": 0,
        "expect_names": set(),
    },
    # (c) Three components, two collide on one path "/reports", the third is
    # clean -> exactly one failure, for the one collided path.
    {
        "given": [
            _component("alpha", ["/reports", "/alpha"]),
            _component("beta", ["/reports"]),
            _component("gamma", ["/gamma", "/settings"]),
        ],
        "expect_count": 1,
        "expect_names": {"alpha", "beta"},
    },
]


def probe_test_route_isolation():
    """test_route_isolation returns one route_collision failure per path two components share, naming both, and empty when every path is unique."""
    bad = []
    for case in _CASES:
        given = case["given"]
        findings = test_route_isolation(components=given)

        if len(findings) != case["expect_count"]:
            bad.append(
                f"test_route_isolation({given}) produced {len(findings)} findings, "
                f"expected {case['expect_count']}"
            )
            continue

        for finding in findings:
            if finding["code"] != "route_collision":
                bad.append(
                    f"test_route_isolation({given}) -> finding code "
                    f"{finding['code']!r}, expected 'route_collision'"
                )
            if finding["kind"] != "failure":
                bad.append(
                    f"test_route_isolation({given}) -> finding kind "
                    f"{finding['kind']!r}, expected 'failure'"
                )
            missing = {n for n in case["expect_names"] if n not in finding["message"]}
            if missing:
                bad.append(
                    f"test_route_isolation({given}) -> message "
                    f"{finding['message']!r} does not name {missing}"
                )
    return bad


def run():
    bad = probe_test_route_isolation()
    for line in bad:
        print(line)
    print(f"probe_test_route_isolation: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
