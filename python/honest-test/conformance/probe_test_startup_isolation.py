"""Conformance fragment for the test_startup_isolation scenario (honest-test.feature).

Scenario: test_startup_isolation reports startup_cascade when one component's
load failure breaks another.
  Then with load_component the injected loader driving the genuine load, when one
  component fails to load every other must still load.
  And it returns a startup_cascade failure Finding when a failure in one component
  causes another to fail to load, empty when each component's load failure is isolated.
  And the effect of loading belongs to the injected loader; honest-test only observes
  which loads then fail.

load_component is injected as a real plain function, never a mock. The probe defines
two loaders. The isolated loader lets 'b' fail to load on its own while 'a' and 'c'
load regardless, so no failure cascades and the result is empty. The cascading loader
models shared state so that once 'b' has failed, 'c' can no longer load, so one
startup_cascade failure arises. The probe calls the real
honest_test.test_startup_isolation on each and checks the findings.

This is its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import test_startup_isolation


def _component(name):
    """A minimal Component dict: name, empty template, no routes."""
    return {"name": name, "template": "", "routes": []}


def _isolated_loader(component):
    """'b' fails to load on its own; every other component loads fine regardless."""
    if component["name"] == "b":
        raise RuntimeError("component 'b' cannot load")
    return None


def _make_cascading_loader():
    """Shared state: once 'b' has failed to load, 'c' can no longer load either."""
    state = {"b_failed": False}

    def load(component):
        name = component["name"]
        if name == "b":
            state["b_failed"] = True
            raise RuntimeError("component 'b' cannot load")
        if name == "c" and state["b_failed"]:
            raise RuntimeError("component 'c' cannot load after 'b' failed")
        return None

    return load


# 'b' is the trigger that fails; it is placed last so that after it fails the main
# loop ends, and the cascade onto 'c' is observed exactly once in the recheck of the
# remaining components (spec section 7.3).
_COMPONENTS = [_component("a"), _component("c"), _component("b")]

_CASES = [
    # Isolated failure: 'b' fails alone, 'a' and 'c' still load -> no cascade.
    {
        "load_component": _isolated_loader,
        "expect_count": 0,
        "expect_code": None,
    },
    # Cascading failure: 'b' failing knocks out 'c' -> one startup_cascade failure.
    {
        "load_component": _make_cascading_loader(),
        "expect_count": 1,
        "expect_code": "startup_cascade",
    },
]


def probe_test_startup_isolation():
    """test_startup_isolation returns a startup_cascade failure when one component's load failure breaks another, and nothing when each component's load failure is isolated."""
    bad = []
    for case in _CASES:
        got = test_startup_isolation(_COMPONENTS, case["load_component"])
        if len(got) != case["expect_count"]:
            bad.append(
                f"test_startup_isolation({_COMPONENTS}) produced {len(got)} "
                f"finding(s): {got}, expected {case['expect_count']}"
            )
            continue
        if case["expect_code"] is not None:
            finding = got[0]
            if finding["code"] != case["expect_code"]:
                bad.append(
                    f"test_startup_isolation(...) -> code {finding['code']!r}, "
                    f"expected {case['expect_code']!r}"
                )
            if finding["kind"] != "failure":
                bad.append(
                    f"test_startup_isolation(...) -> kind {finding['kind']!r}, "
                    "expected 'failure'"
                )
    return bad


def run():
    bad = probe_test_startup_isolation()
    for line in bad:
        print(line)
    print(f"probe_test_startup_isolation: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
