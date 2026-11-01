"""Honest test for the startup_check scenario (features/honest-check.feature).

startup_check(paths, on_error, severity) is the development-mode startup door.
It hands paths to check_paths, runs the startup-eligible rules, decides whether
any finding reaches the blocking severity, and acts on on_error:
  - 'warn'  prints the blocking violations to stderr and returns the diagnostics,
            letting startup continue (no raise);
  - 'raise' raises HonestCheckError carrying the report;
  - 'halt'  prints and exits the process with code 1.

Blocking finding used here: a source that does not parse. A parse failure fires
HC-SYN, a startup-eligible rule at error severity already built into check_source.
(The .hd note's own example, the empty-chain HC007 trigger, needs declaration-graph
extraction that is not built yet; see bead honest-framework-4gv.)

Limit, stated on purpose: the 'halt' process-exit path is left unexercised.
Driving it would call sys.exit(1) and end this test process, so it cannot be
probed in-process. That is a coverage limit of this probe, not a gap in the spec.
"""

import io
import os
import tempfile
from contextlib import redirect_stderr

from honest_check import startup_check, HonestCheckError

# A file that does not parse -> HC-SYN at error severity -> a blocking finding.
_UNPARSEABLE = "def (:\n"
# Valid Python with no framework construction -> no finding -> clean.
_CLEAN = "x = 1\n"

_CASES = [
    # Blocking source, on_error 'warn': returns a non-empty list carrying an
    # HC-SYN finding, prints to stderr, and does not raise.
    {
        "source": _UNPARSEABLE,
        "on_error": "warn",
        "severity": "error",
        "expect": {"raised": False, "hc_syn_in_result": True, "stderr_nonempty": True},
    },
    # Same blocking source, on_error 'raise': raises HonestCheckError.
    {
        "source": _UNPARSEABLE,
        "on_error": "raise",
        "severity": "error",
        "expect": {"raised": True},
    },
    # Clean source, on_error 'warn': the explicit absence case. Returns [], no raise.
    {
        "source": _CLEAN,
        "on_error": "warn",
        "severity": "error",
        "expect": {"raised": False, "result": []},
    },
]


def _rule_id(diagnostic):
    """Pull rule_id from one Diagnostic, whether it is a dict or a record object."""
    if isinstance(diagnostic, dict):
        return diagnostic.get("rule_id")
    return getattr(diagnostic, "rule_id", None)


def _run(source, on_error, severity):
    """Write source to a real temp .py file, call startup_check on it, and report
    what it did: whether it raised, what it returned, and whether it wrote stderr."""
    fd, path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(source)
        err = io.StringIO()
        try:
            with redirect_stderr(err):
                result = startup_check([path], on_error, severity)
        except HonestCheckError:
            return {"raised": True}
        return {
            "raised": False,
            "result": result,
            "hc_syn_in_result": any(_rule_id(d) == "HC-SYN" for d in result),
            "stderr_nonempty": err.getvalue() != "",
        }
    finally:
        os.remove(path)


def probe_startup_check():
    """A blocking finding under 'warn' prints to stderr and returns the diagnostics
    (HC-SYN present, no raise); under 'raise' it raises HonestCheckError; and a clean
    source under 'warn' returns [] without raising."""
    bad = []
    for case in _CASES:
        observed = _run(case["source"], case["on_error"], case["severity"])
        for key, want in case["expect"].items():
            got = observed.get(key, "<missing>")
            if got != want:
                bad.append(
                    f"startup_check(on_error={case['on_error']!r}, "
                    f"severity={case['severity']!r}) on {case['source']!r}: "
                    f"{key} -> {got!r}, expected {want!r}"
                )
    return bad
