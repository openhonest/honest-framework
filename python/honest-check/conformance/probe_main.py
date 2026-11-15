"""Honest probe for honest-check's main (feature Scenario: main).

main is the CLI door. It hands argv straight to run_check and turns run_check's
answer into the process exit: on an ExitCode it exits the process with it (0 is
success, 1 is the failed gate); on the declaration-read Fault it discharges it at
exit code 2, raising HonestCheckError carrying the Fault's problem and remedy.

This is a near-integration probe over a REAL temp tree, not mocks. The door "exits
the process", but the declared signature returns an ExitCode, so this probe treats
either a returned code or a SystemExit as equally valid and compares the code:
  - clean tree -> exit code 0,
  - tree with a bare `if` -> exit code 1,
  - --declaration naming a missing .hd -> HonestCheckError raised (exit code 2).
stderr is captured so a printing door does not pollute the run.

A do-nothing stub (returns None) fails the clean case (None is not 0); a stub
returning '0' fails the `if` case (expects 1) and the Fault case, so the probe is
not vacuous.

GAPS: (1) the scenario does not fix whether main RETURNS the ExitCode or calls
sys.exit, so the probe accepts both. (2) It does not fix the string-vs-int exit
encoding, so the probe normalises with str(). (3) For the read failure the
scenario fixes "raising HonestCheckError"; the probe also accepts SystemExit code
2, since both discharge the Fault as exit 2, and flags that an impl using
sys.exit(2) would not match the literal HonestCheckError. (4) the bare-`if` ->
exit 1 chain rests on the rule catalogue and adoption table, not the main
scenario.
"""
import contextlib
import io
import tempfile
from pathlib import Path

_CLEAN = "def choose(flag):\n    return 1\n"
_BAD_IF = "def choose(flag):\n    if flag:\n        return 1\n    return 0\n"


def _invoke(main, argv):
    """Call main under captured stderr; report how it ended as a (kind, payload)
    pair: ('return', value), ('exit', code) or ('raise', exception class name)."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stderr(buf):
            value = main(argv)
        return ("return", value)
    except SystemExit as se:
        return ("exit", se.code)
    except Exception as exc:
        return ("raise", type(exc).__name__)


def probe_main():
    """main turns run_check's answer into exit 0 on a clean tree, 1 on a violation, and HonestCheckError on a missing --declaration."""
    try:
        from honest_check import main
    except ImportError as exc:
        return [f"cannot import main: {exc}"]

    bad = []

    # Clean tree -> exit code 0 (returned or via SystemExit).
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "clean.py").write_text(_CLEAN)
        kind, payload = _invoke(main, [d])
        if kind == "raise":
            bad.append(f"main([clean tree]) raised {payload}, expected exit code 0")
        elif str(payload) != "0":
            bad.append(f"main([clean tree]) {kind} {payload!r}, expected exit code 0")

    # Tree with a bare `if` -> exit code 1.
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "bad.py").write_text(_BAD_IF)
        kind, payload = _invoke(main, [d])
        if kind == "raise":
            bad.append(f"main([tree with `if`]) raised {payload}, expected exit code 1")
        elif str(payload) != "1":
            bad.append(f"main([tree with `if`]) {kind} {payload!r}, expected exit code 1")

    # --declaration naming a missing .hd -> HonestCheckError (exit code 2).
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "clean.py").write_text(_CLEAN)
        missing = str(Path(d) / "nope.hd")
        kind, payload = _invoke(main, [d, "--declaration", missing])
        discharged = (kind == "raise" and payload == "HonestCheckError") or (
            kind == "exit" and str(payload) == "2"
        )
        if not discharged:
            bad.append(
                f"main([tree, --declaration <missing>]) {kind} {payload!r}, "
                f"expected HonestCheckError raised (the Fault discharged as exit code 2)"
            )

    return bad
