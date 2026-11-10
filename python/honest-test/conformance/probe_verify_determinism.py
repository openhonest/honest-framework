"""Conformance fragment for the verify_under_monitor scenario (honest-test.feature ~line 211).

Scenario: verify_under_monitor runs a link under the call monitor and warns
  nondeterminism_detected for a non-boundary link.
  Then it runs the link inside the injected call monitor, which traps the symbols
  on the non-deterministic watch list, and returns a nondeterminism_detected
  warning when the monitor recorded such a call and the link is not declared a
  boundary (spec section 4.5).
  And it returns the warning as a one-element list, or the empty list. The warning
  reports and does not block.

Cases are data; one pure probe feeds them to the real function and returns a list
of failure strings (empty when every case holds). No classes, no mocks, no
monkeypatching of production code: the link is a real Callable injected as test
input, boundary-ness is set with honest-type's real link() decorator, and the
monitor is a real record-and-restore recording function defined below. It calls
the real honest_test.verify_under_monitor.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.

ASSUMED MONITOR CALLING CONVENTION (flagged as a gap; see the GAPS block in the
report): the injected `monitor` is a callable `monitor(link, test_manifest)` that
runs the link once under instrumentation and returns the record of watched
non-deterministic calls the link made, as a list of symbol names (the empty list
when none were detected). verify_under_monitor is assumed to call the monitor to run
the link, treat a non-empty record as detected non-determinism, and read the link's
boundary flag from honest-type's link_meta (the __honest_link__ metadata set by the
link() decorator). Neither the monitor's signature/return shape nor the
boundary-flag source is pinned by the .hd note or spec section 4.5.
"""

import time

from honest_type.chains import link

from honest_test import verify_under_monitor


# --- The injected call monitor: a real record-and-restore recording function. ---
# It temporarily wraps time.time so each call is recorded, runs the link, then
# restores the original unchanged. This is the framework's record-and-restore
# instrumentation pattern (spec 4.5 / .hd section 4.8), not a behaviour-changing
# stand-in: the original is put back, so the link's result is untouched. It is a
# genuine detector, not a hardcoded verdict.
def call_monitor(link_under_test, test_manifest):
    """Run the link under instrumentation; return the watched non-deterministic
    calls it made as a list of symbol names (empty when none were detected)."""
    detected = []
    original_time = time.time

    def recording_time():
        detected.append("time.time")
        return original_time()

    time.time = recording_time
    try:
        link_under_test(test_manifest)
    finally:
        time.time = original_time
    return detected


# --- The links, real test input. ---
def nondeterministic_link(manifest):
    """A non-boundary link that reaches a non-deterministic source (time.time)."""
    return {**manifest, "stamp": time.time()}


def deterministic_link(manifest):
    """A non-boundary link that touches no non-deterministic source."""
    return {**manifest, "seen": True}


@link(boundary=True)
def boundary_nondeterministic_link(manifest):
    """A link declared a boundary that reaches a non-deterministic source. A
    boundary is exempt: non-determinism there is expected, so no warning."""
    return {**manifest, "stamp": time.time()}


_CASES = [
    # A NON-boundary link that calls a non-deterministic source, under a monitor
    # that detects it: exactly one nondeterminism_detected warning. This is the
    # literal non-trivial case a stub returning [] cannot pass.
    {
        "link": nondeterministic_link,
        "test_manifest": {"color": "red", "size": "small"},
        "expect_codes": ["nondeterminism_detected"],
    },
    # A NON-boundary link that is deterministic: the monitor records nothing, so
    # the empty list.
    {
        "link": deterministic_link,
        "test_manifest": {"color": "red", "size": "small"},
        "expect_codes": [],
    },
    # A BOUNDARY link that calls a non-deterministic source: exempt, so the empty
    # list even though the monitor records the call.
    {
        "link": boundary_nondeterministic_link,
        "test_manifest": {"color": "red", "size": "small"},
        "expect_codes": [],
    },
]


def probe_verify_determinism():
    """verify_under_monitor returns one nondeterminism_detected warning when a non-boundary link calls a watched non-deterministic source under the monitor, and the empty list when the link is deterministic or declared a boundary."""
    bad = []
    for case in _CASES:
        got = verify_under_monitor(case["link"], case["test_manifest"], call_monitor, "nondeterminism")
        if not isinstance(got, list):
            bad.append(
                f"verify_under_monitor({case['link'].__name__}) -> {got!r}, "
                f"expected a list"
            )
            continue
        got_codes = [f["code"] for f in got]
        if got_codes != case["expect_codes"]:
            bad.append(
                f"verify_under_monitor({case['link'].__name__}) produced codes "
                f"{got_codes}, expected {case['expect_codes']}"
            )
            continue
        # For the warning case, pin the grade too: a nondeterminism_detected
        # finding is a warning, never a failure or rejection.
        for finding in got:
            if finding["kind"] != "warning":
                bad.append(
                    f"verify_under_monitor({case['link'].__name__}) finding "
                    f"{finding['code']} has kind {finding['kind']!r}, "
                    f"expected 'warning'"
                )
    return bad


def run():
    bad = probe_verify_determinism()
    for line in bad:
        print(line)
    print(f"probe_verify_determinism: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
