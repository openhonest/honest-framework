"""Conformance fragment for the test_body_violations scenario (honest-test.feature).

Scenario: test_body_violations returns one rejection per statement that rebinds a
  call target at runtime.
  Then it returns one rejection Finding per statement that rebinds a call target at
  runtime: a monkeypatch fixture (setattr, setitem, delattr, setenv), a mock.patch
  or patch.object or an installed Mock, a setattr on an imported module, class or
  function, or an imported symbol rebound by attribute assignment.
  And the framework's own record-and-restore instrumentation (io_monitor,
  call_monitor) is not a violation and never appears.
  And an empty list means the test body is honest.

Cases are data; one pure probe feeds them to the real function and returns a list
of failure strings (empty when every case holds). No classes, no stand-ins: it
calls the real honest_test.test_body_violations on Python test-body source STRINGS
and asserts, per rejection, code == "test_body_dishonest" and kind == "rejection",
plus the per-statement count.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import test_body_violations

# Each case: a test-module source string, and how many rejection Findings
# test_body_violations must return for it. The source strings are the probe's own
# inputs; the counts, codes and kinds they must produce are fixed by the scenario
# ("one rejection per statement that rebinds a call target") and the .hd
# (test_body_dishonest / rejection).
_CASES = [
    # An honest body: plain asserts, the dependency passed as a parameter. Nothing
    # is rebound, so the rule fires on nothing.
    {
        "source": (
            "def test_uses_injected_boundary(clock_plug):\n"
            "    result = compute(now=clock_plug)\n"
            "    assert result == 42\n"
        ),
        "expect_count": 0,
    },
    # A monkeypatch fixture rebinds a call target at runtime: one rejection.
    {
        "source": (
            "def test_patches_time(monkeypatch):\n"
            "    monkeypatch.setattr(service, 'now', lambda: 0)\n"
            "    assert service.elapsed() == 0\n"
        ),
        "expect_count": 1,
    },
    # mock.patch installed as a decorator over the test: one rejection.
    {
        "source": (
            "from unittest.mock import patch\n"
            "\n"
            "@patch('service.now')\n"
            "def test_patched(patched_now):\n"
            "    assert service.elapsed() == 0\n"
        ),
        "expect_count": 1,
    },
    # An imported symbol rebound by attribute assignment: one rejection.
    {
        "source": (
            "import service\n"
            "\n"
            "def test_rebinds():\n"
            "    service.now = lambda: 0\n"
            "    assert service.elapsed() == 0\n"
        ),
        "expect_count": 1,
    },
    # TWO rebinding statements in one body: one rejection per statement, so two.
    # A monkeypatch.setattr and an attribute assignment, to stress that the count
    # is per statement and spans more than one rebinding form.
    {
        "source": (
            "def test_two(monkeypatch):\n"
            "    monkeypatch.setattr(service, 'now', lambda: 0)\n"
            "    service.clock = lambda: 1\n"
            "    assert service.elapsed() == 0\n"
        ),
        "expect_count": 2,
    },
    # monkeypatch.setitem rebinds a dict entry at runtime: one rejection. The rule
    # names four monkeypatch methods (setattr, setitem, delattr, setenv); this case
    # and the two below exercise the forms the setattr case alone does not, so each
    # member of the method set is a tested recognizer, not a dead constant.
    {
        "source": (
            "def test_item(monkeypatch):\n"
            "    monkeypatch.setitem(config, 'now', 0)\n"
            "    assert run() == 0\n"
        ),
        "expect_count": 1,
    },
    # monkeypatch.delattr removes a call target at runtime: one rejection.
    {
        "source": (
            "def test_del(monkeypatch):\n"
            "    monkeypatch.delattr(service, 'now')\n"
            "    assert service.elapsed() == 0\n"
        ),
        "expect_count": 1,
    },
    # monkeypatch.setenv rebinds an environment variable at runtime: one rejection.
    # The fourth monkeypatch method, so all four are exercised by this probe alone.
    {
        "source": (
            "def test_env(monkeypatch):\n"
            "    monkeypatch.setenv('NOW', '0')\n"
            "    assert run() == 0\n"
        ),
        "expect_count": 1,
    },
    # mock.patch written as an ATTRIBUTE call (module.patch(...)), not the bare
    # `patch(...)` name the decorator case above uses: one rejection. This is the
    # _PATCH_ATTRS branch, where the call's attribute name must be recognised.
    {
        "source": (
            "from unittest import mock\n"
            "\n"
            "def test_attr_patch():\n"
            "    mock.patch('service.now')\n"
            "    assert service.elapsed() == 0\n"
        ),
        "expect_count": 1,
    },
    # patch.object(...), the other _PATCH_ATTRS member: one rejection. With the
    # attribute-patch case above, both members of the patch-attr set are exercised.
    {
        "source": (
            "from unittest.mock import patch\n"
            "\n"
            "def test_patch_object():\n"
            "    patch.object(service, 'now')\n"
            "    assert service.elapsed() == 0\n"
        ),
        "expect_count": 1,
    },
    # Carve-out: the framework's own record-and-restore instrumentation used as a
    # context manager (call_monitor / io_monitor, spec sections 4.4, 4.5, 4.8). It
    # observes a watch-list symbol and restores the original rather than installing
    # a behaviour-changing stand-in, so it is never a violation: empty list.
    {
        "source": (
            "from honest_test import call_monitor\n"
            "\n"
            "def test_observes_only():\n"
            "    with call_monitor(WATCH_LIST):\n"
            "        result = pure_fn(5)\n"
            "    assert result == 25\n"
        ),
        "expect_count": 0,
    },
]


def probe_test_body_violations():
    """test_body_violations returns one test_body_dishonest rejection per statement that rebinds a call target, none for an honest body or the framework's record-and-restore monitors."""
    bad = []
    for case in _CASES:
        findings = test_body_violations(case["source"])
        if len(findings) != case["expect_count"]:
            bad.append(
                f"test_body_violations({case['source']!r}) produced "
                f"{len(findings)} rejection(s), expected {case['expect_count']}"
            )
            continue
        for finding in findings:
            if finding["code"] != "test_body_dishonest":
                bad.append(
                    f"test_body_violations({case['source']!r}) emitted code "
                    f"{finding['code']!r}, expected 'test_body_dishonest'"
                )
            if finding["kind"] != "rejection":
                bad.append(
                    f"test_body_violations({case['source']!r}) emitted kind "
                    f"{finding['kind']!r}, expected 'rejection'"
                )
            # The rejection must carry the fix the spec specifies (section 4.8): pass the
            # dependency as a parameter, or inject a boundary plug as an argument. Asserting
            # both halves keeps the fix text from being silently emptied.
            message = finding["message"]
            for phrase in ("pass the dependency as a parameter", "inject a boundary plug as an argument"):
                if phrase not in message:
                    bad.append(
                        f"test_body_violations({case['source']!r}) rejection message "
                        f"{message!r} is missing the fix phrase {phrase!r}"
                    )
    return bad


def run():
    bad = probe_test_body_violations()
    for line in bad:
        print(line)
    print(f"probe_test_body_violations: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
