"""Conformance fragment for the two run_body_check scenarios (honest-test.feature).

Scenario (honest body): run_body_check runs the verdict and returns an empty list.
  Then it runs test_body_violations over the one test module's source the door read
  And it returns the empty list when the test body is honest.

Scenario (dishonest body): run_body_check returns one rejection Finding per
  rebinding statement.
  Then it runs test_body_violations over the source and returns the list of
  rejection Findings for the door to act on.

run_body_check is a pure orchestrator over a source STRING: it runs the verdict and
returns what it produced. Cases are data; one pure probe feeds each test-module
source string to the real honest_test.run_body_check and returns a list of failure
strings (empty when every case holds). No classes, no mocks: a sibling fragment
writes test_body_violations, so this probe calls only run_body_check.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import run_body_check

# An honest test body: plain asserts, the dependency passed as a parameter, no
# runtime rebinding anywhere. The verdict must be the empty list.
_HONEST = '''
def test_add():
    assert add(2, 3) == 5

def test_with_injected_boundary(clock):
    assert now(clock=clock) == 0
'''

# A dishonest body with exactly ONE rebinding statement: one monkeypatch.setattr
# that installs a stand-in call target. Exactly one rejection, one per statement.
_ONE_REBIND = '''
def test_patched(monkeypatch):
    monkeypatch.setattr(service, "fetch", lambda: 1)
    assert service.fetch() == 1
'''

# A dishonest body with TWO rebinding statements: two monkeypatch.setattr calls.
# Two rejections, pinning the per-statement count (one rejection per statement,
# not one per test body).
_TWO_REBINDS = '''
def test_patched_twice(monkeypatch):
    monkeypatch.setattr(service, "fetch", lambda: 1)
    monkeypatch.setattr(service, "store", lambda x: None)
    assert service.fetch() == 1
'''

_CASES = [
    {"name": "honest body", "source": _HONEST, "expect_count": 0},
    {"name": "one rebinding statement", "source": _ONE_REBIND, "expect_count": 1},
    {"name": "two rebinding statements", "source": _TWO_REBINDS, "expect_count": 2},
]


def probe_run_body_check():
    """run_body_check returns the empty list for an honest test body and one rejection Finding (code test_body_dishonest, kind rejection) per rebinding statement for a dishonest one."""
    bad = []
    for case in _CASES:
        got = run_body_check(source=case["source"])
        if len(got) != case["expect_count"]:
            bad.append(
                f"run_body_check({case['name']}) produced {len(got)} finding(s), "
                f"expected {case['expect_count']}"
            )
            continue
        for finding in got:
            if finding["code"] != "test_body_dishonest":
                bad.append(
                    f"run_body_check({case['name']}) finding code is "
                    f"{finding['code']!r}, expected 'test_body_dishonest'"
                )
            if finding["kind"] != "rejection":
                bad.append(
                    f"run_body_check({case['name']}) finding kind is "
                    f"{finding['kind']!r}, expected 'rejection'"
                )
    return bad


def run():
    bad = probe_run_body_check()
    for line in bad:
        print(line)
    print(f"probe_run_body_check: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
