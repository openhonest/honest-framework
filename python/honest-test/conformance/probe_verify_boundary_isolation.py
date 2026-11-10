"""Conformance fragment for the verify_under_monitor scenario (honest-test.feature ~line 203).

Scenario: verify_under_monitor runs a link under the I/O monitor and warns
  io_detected for a non-boundary link.
  Then it runs the link under the injected I/O monitor and returns an io_detected
  warning Finding when the monitor recorded an I/O call and the link is not
  declared a boundary, because a non-boundary link must perform no I/O.
  And it returns the warning as a one-element list, or the empty list when no I/O
  was detected or the link is a declared boundary. The warning reports and does
  not block.

Cases are data; one pure probe feeds them to the real function and returns a list
of failure strings (empty when every case holds). No classes, no mocks, no
monkeypatching: the links are real Callables injected as test input, declared with
honest-type's real @link() so their boundary flag is honest metadata, and the
monitor is a real recording function injected as the io_monitor plug. A Manifest is
a plain dict (honest-type's manifest shape). It calls the real
honest_test.verify_under_monitor.

MONITOR INTERFACE (pinned at the code stage, shared with verify_under_monitor §4.5):
the injected monitor is a callable `monitor(link, test_manifest)` that runs the link
and returns the record of detected calls as a collection. An empty record means
nothing was detected; a non-empty record means it was. verify_under_monitor
warns when the record is non-empty and the link is not a declared boundary. The
boundary flag is read through honest-type's link metadata the @link() decorator
attaches. The sibling determinism check uses the same collection interface, so one
monitor shape serves both.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_type import link

from honest_test import verify_under_monitor

# A cooperating watched I/O sink. It stands in for a known I/O function (a file
# write, a socket send) the framework's io_monitor would patch. It records that it
# ran; it is a real recording function, not a mock, and it changes no link result.
_IO_LOG = []


def watched_write(payload):
    """A watched I/O call: records that it ran and returns the payload unchanged."""
    _IO_LOG.append(payload)
    return payload


def recording_monitor(link_fn, manifest):
    """The injected io_monitor plug: runs the link and returns the record of the
    watched I/O calls that happened during the run. Record-and-restore in spirit:
    it reads the watch log before and after, so it changes no result and reaches for
    no global state of its own. An empty record means no I/O; a non-empty record
    means I/O was detected. honest-test takes this record back and warns when it is
    non-empty for a non-boundary link."""
    before = len(_IO_LOG)
    link_fn(manifest)
    return _IO_LOG[before:]


# A non-boundary link that performs I/O: it calls the watched sink. The monitor
# detects it, and since the link is not declared a boundary, this must warn.
@link(boundary=False)
def noisy_non_boundary_link(manifest):
    """A link not declared a boundary that performs I/O it should not."""
    watched_write(manifest)
    return {**manifest, "seen": True}


# A non-boundary link that performs no I/O: clean, nothing to warn about.
@link(boundary=False)
def quiet_non_boundary_link(manifest):
    """A pure, I/O-free non-boundary link."""
    return {**manifest, "seen": True}


# A declared boundary link that performs I/O: I/O at a declared boundary is
# expected, so it is exempt and must produce no warning.
@link(boundary=True)
def noisy_boundary_link(manifest):
    """A declared boundary link whose I/O is expected and allowed."""
    watched_write(manifest)
    return {**manifest, "sent": True}


_CASES = [
    # A non-boundary link that performs I/O, under a monitor that detects it:
    # exactly one io_detected warning, returned as a one-element list.
    {
        "link": noisy_non_boundary_link,
        "test_manifest": {"color": "red", "size": "small"},
        "expect_codes": ["io_detected"],
    },
    # A non-boundary link that performs no I/O: the empty list, written out so a
    # stub returning [] is not the only thing that passes.
    {
        "link": quiet_non_boundary_link,
        "test_manifest": {"color": "red", "size": "small"},
        "expect_codes": [],
    },
    # A declared boundary link that performs I/O: exempt, the empty list.
    {
        "link": noisy_boundary_link,
        "test_manifest": {"color": "red", "size": "small"},
        "expect_codes": [],
    },
]


def probe_verify_boundary_isolation():
    """verify_under_monitor returns one io_detected warning Finding when a non-boundary link performs I/O the monitor records, and the empty list when no I/O was detected or the link is a declared boundary."""
    bad = []
    for case in _CASES:
        got = verify_under_monitor(
            case["link"], case["test_manifest"], recording_monitor, "io"
        )
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
        # For the warning case, pin the grade too: an io_detected finding is a
        # warning that reports and does not block, never a failure or rejection.
        for finding in got:
            if finding["kind"] != "warning":
                bad.append(
                    f"verify_under_monitor({case['link'].__name__}) finding "
                    f"{finding['code']} has kind {finding['kind']!r}, "
                    f"expected 'warning'"
                )
    return bad


def run():
    bad = probe_verify_boundary_isolation()
    for line in bad:
        print(line)
    print(f"probe_verify_boundary_isolation: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
