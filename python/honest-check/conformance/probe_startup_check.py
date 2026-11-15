"""Honest probe for honest-check's startup_check (feature Scenario: startup_check).

startup_check is the startup door. It hands its paths and severity to check_paths,
gets back a StartupFindings, and acts per on_error over the blocking subset:
'warn' prints the blocking violations to stderr and returns the full all list and
lets startup continue; 'raise' raises HonestCheckError carrying the full all list;
'halt' prints and exits the process with code 1. It runs only the startup_rules
set, with HC-SYN first "because a file that does not parse has no architecture to
check."

This is a near-integration probe over a REAL temp tree, not mocks. The violation
is a file that does not parse, which the scenario itself names as the HC-SYN case
and which is a startup-eligible rule — so it fires at startup regardless of import
aliasing. stderr is captured with contextlib.redirect_stderr.

Two of the three on_error branches are probed directly:
  - 'warn' over a parse failure: prints to stderr, returns the non-empty findings
    list, does not raise.
  - 'raise' over the same failure: raises HonestCheckError (matched by class name,
    so the probe does not depend on where the error type is importable from).

A stub returning [] fails the 'warn' case (empty return) and the 'raise' case
(no exception), so the probe is not vacuous.

NOT PROBED: the 'halt' branch exits the process. Executing it in-process would
kill this conformance run (and os._exit would not even be catchable), and the
CLI entry point to drive it in a subprocess does not exist during the clean-slate
rebuild. It is flagged in the report, not faked.

GAP: the scenario fixes the on_error branch behaviours but does not fix that a
parse failure maps to HC-SYN at error severity — that mapping is the rule
catalogue's (section 2.3 / the conformance suite). This probe only asserts that
SOME blocking violation is produced and printed/raised, never a specific rule_id.
"""
import contextlib
import io
import tempfile
from pathlib import Path

# A file that does not parse: the HC-SYN startup case the scenario names.
_BROKEN = "def broken(  :::\n"


def probe_startup_check():
    """startup_check prints blocking violations to stderr under 'warn' and raises HonestCheckError under 'raise'."""
    try:
        from honest_check import startup_check
    except ImportError as exc:
        return [f"cannot import startup_check: {exc}"]

    bad = []

    # on_error 'warn' over a file that does not parse: print to stderr, return the
    # full (non-empty) findings list, do not raise.
    with tempfile.TemporaryDirectory() as d:
        broken = Path(d) / "broken.py"
        broken.write_text(_BROKEN)
        buf = io.StringIO()
        result = None
        try:
            with contextlib.redirect_stderr(buf):
                result = startup_check([str(broken)], "warn", "error")
        except Exception as exc:
            bad.append(
                f"startup_check([parse-failure], 'warn', 'error') raised "
                f"{type(exc).__name__}: {exc}, expected it to print and return"
            )
        if result is not None:
            if not isinstance(result, list) or not result:
                bad.append(
                    f"startup_check('warn').return -> {result!r}, "
                    f"expected the non-empty full findings list"
                )
            if buf.getvalue() == "":
                bad.append(
                    "startup_check('warn') wrote nothing to stderr, "
                    "expected the blocking parse-failure violation printed"
                )

    # on_error 'raise' over the same parse failure: raise HonestCheckError.
    with tempfile.TemporaryDirectory() as d:
        broken = Path(d) / "broken.py"
        broken.write_text(_BROKEN)
        raised = None
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                startup_check([str(broken)], "raise", "error")
        except Exception as exc:
            raised = type(exc).__name__
        if raised != "HonestCheckError":
            bad.append(
                f"startup_check([parse-failure], 'raise', 'error') raised {raised!r}, "
                f"expected HonestCheckError"
            )

    return bad
