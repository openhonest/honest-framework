# scenario: startup_check
# inherits: hd=python/honest-check/honest-check.hd::startup_check -> feature=specs/features/honest-check.feature::startup_check
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

The probe checks all three on_error branches. Under 'halt', clean source returns
its empty findings and a parse failure writes the HC-SYN diagnostic to stderr
before raising SystemExit with status 1.
"""
import contextlib
import io
import tempfile
from pathlib import Path

# A file that does not parse: the HC-SYN startup case the scenario names.
_BROKEN = "def broken(  :::\n"
_CLEAN = "answer = 42\n"


def probe_startup_check():
    """startup_check reports findings and enforces the selected startup policy."""
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

    with tempfile.TemporaryDirectory() as d:
        clean = Path(d) / "clean.py"
        clean.write_text(_CLEAN)
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                result = startup_check([str(clean)], "halt", "error")
        except SystemExit as exc:
            bad.append(f"startup_check([clean], 'halt', 'error') exited with {exc.code!r}")
        else:
            if result != []:
                bad.append(
                    f"startup_check([clean], 'halt', 'error') returned {result!r}, "
                    "expected the empty findings list"
                )

        broken = Path(d) / "broken.py"
        broken.write_text(_BROKEN)
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr):
                startup_check([str(broken)], "halt", "error")
        except SystemExit as exc:
            if type(exc.code) is not int or exc.code != 1:
                bad.append(
                    f"startup_check([parse-failure], 'halt', 'error') exited with "
                    f"{exc.code!r}, expected 1"
                )
        else:
            bad.append("startup_check([parse-failure], 'halt', 'error') returned, expected exit 1")

        if not any(
            line.startswith(f"{broken}: error HC-SYN: ") for line in stderr.getvalue().splitlines()
        ):
            bad.append(
                "startup_check([parse-failure], 'halt', 'error') did not write "
                f"the HC-SYN error for {broken} to stderr"
            )

    return bad
