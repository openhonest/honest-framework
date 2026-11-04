"""Conformance fragment for the verify_boundary_isolation scenario (honest-test.feature ~line 203).

Scenario: verify_boundary_isolation runs a link under the I/O monitor and warns
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
honest_test.verify_boundary_isolation.

ASSUMED INTERFACE (flagged as a gap in the report): the .hd note commits to an
INJECTED monitor callable ("passed in as a callable so honest-test runs the link
under it and takes back the record of detected calls"), but does not pin the exact
calling convention or the record shape. This probe assumes:
  - honest-test invokes `monitor(link, test_manifest)`;
  - the monitor runs `link(test_manifest)` and returns a record dict whose
    "detected_io" flag is True iff a watched I/O call happened, and whose "result"
    holds the link's return value;
  - verify_boundary_isolation reads the boundary flag through honest-type's
    link_meta()/__honest_link__ metadata the @link() decorator attaches.
If the real function expects a different convention (context-manager monitor, a
different record key, or a `link.boundary` attribute instead of link metadata),
this probe will need to follow it once that interface is pinned.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_type import link

from honest_test import verify_boundary_isolation

# A cooperating watched I/O sink. It stands in for a known I/O function (a file
# write, a socket send) the framework's io_monitor would patch. It records that it
# ran; it is a real recording function, not a mock, and it changes no link result.
_IO_LOG = []


def watched_write(payload):
    """A watched I/O call: records that it ran and returns the payload unchanged."""
    _IO_LOG.append(payload)
    return payload


def recording_monitor(link_fn, manifest):
    """The injected io_monitor plug: runs the link and reports whether any watched
    I/O call happened. Record-and-restore in spirit — it reads the length of the
    watch log before and after the run, so it changes no result and reaches for no
    global state of its own. Returns the record honest-test takes back."""
    before = len(_IO_LOG)
    result = link_fn(manifest)
    return {"detected_io": len(_IO_LOG) > before, "result": result}


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
    """verify_boundary_isolation returns one io_detected warning Finding when a non-boundary link performs I/O the monitor records, and the empty list when no I/O was detected or the link is a declared boundary."""
    bad = []
    for case in _CASES:
        got = verify_boundary_isolation(
            case["link"], case["test_manifest"], recording_monitor
        )
        if not isinstance(got, list):
            bad.append(
                f"verify_boundary_isolation({case['link'].__name__}) -> {got!r}, "
                f"expected a list"
            )
            continue
        got_codes = [f["code"] for f in got]
        if got_codes != case["expect_codes"]:
            bad.append(
                f"verify_boundary_isolation({case['link'].__name__}) produced codes "
                f"{got_codes}, expected {case['expect_codes']}"
            )
            continue
        # For the warning case, pin the grade too: an io_detected finding is a
        # warning that reports and does not block, never a failure or rejection.
        for finding in got:
            if finding["kind"] != "warning":
                bad.append(
                    f"verify_boundary_isolation({case['link'].__name__}) finding "
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
