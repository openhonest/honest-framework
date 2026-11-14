"""startup_check hands paths to check_paths, decides which findings reach the blocking
severity from the ranked _SEVERITY_RANK map, acts per on_error (warn prints, raise raises,
halt exits), and returns the diagnostic list check_paths produced.

This probe pins three things the rank map and the outcome table decide, each the behaviour
a mutation of cli.py would silently change:

  1. The severity threshold. A finding blocks only when its own rank reaches the threshold
     rank. The matrix below crosses three single-severity sources with three thresholds and
     fixes, for each pair, whether on_error='raise' raises. info ranks below warning ranks
     below error, so lowering, raising or swapping a rank moves a cell. Empties of a rank
     key turn a lookup into a KeyError, which the matrix catches as an unwanted raise.

  2. The outcome each on_error word selects. 'warn' prints the block to stderr and returns;
     'raise' raises HonestCheckError and prints nothing; 'halt' prints and exits 1. A
     two-finding source lets the stderr checks also pin that render_block joins the findings
     with a newline (two lines, each carrying the rule id), not with the empty string.

  3. The two program-bug doors. A clean run under on_error='raise' returns rather than
     raising, so emptying the outcome table's 'raise' key is caught. An on_error word in no
     branch raises HonestCheckError whose message names the word.

Sources, by the severity each yields through check_paths (verified against the real core):
an inline-suppressed dispatch yields one HC-P001 at info; an isinstance classify yields one
HC-P005 at warning; a bare class yields one HC-P003 at error; two classes yield two HC-P003
errors; a plain assignment yields nothing.

Spec authority: section 2.3 (the startup door, its on_error outcomes, and the blocking
severity threshold).
"""

import contextlib
import io
import os
import tempfile

_SOURCE_BY_SEVERITY = {
    "info": (
        "def f(role):\n"
        '    if role == "a":  # honest: ignore HC-P001: dispatch retained pending table\n'
        "        return 1\n"
        '    elif role == "b":\n'
        "        return 2\n"
        '    elif role == "c":\n'
        "        return 3\n"
        "    return 0\n"
    ),
    "warning": "def classify(x):\n    return isinstance(x, int)\n",
    "error": "class Report:\n    pass\n",
}
_TWO_ERRORS = "class A:\n    pass\n\n\nclass B:\n    pass\n"
_CLEAN = "x = 1\n"

# (source severity, threshold, raises) under on_error='raise'. A finding blocks when its
# rank reaches the threshold rank, ranked info < warning < error. These booleans are the
# ordering written out, so a rank shift, swap or key-empty in cli.py moves at least one cell.
_THRESHOLD_MATRIX = [
    ("info", "info", True),
    ("info", "warning", False),
    ("info", "error", False),
    ("warning", "info", True),
    ("warning", "warning", True),
    ("warning", "error", False),
    ("error", "info", True),
    ("error", "warning", True),
    ("error", "error", True),
]


def _write(directory, source):
    path = os.path.join(directory, "source.py")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(source)
    return path


def _call(startup_check, path, on_error, severity):
    """Run startup_check over one path with stderr captured. Returns a tuple
    (kind, payload, stderr): kind is 'return' with the returned list, 'error' with the
    exception, or 'exit' with the SystemExit code."""
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr):
            result = startup_check([path], on_error, severity)
        return ("return", result, stderr.getvalue())
    except SystemExit as exit_signal:
        return ("exit", exit_signal.code, stderr.getvalue())
    except Exception as raised:  # the probe records any raise as data
        return ("error", raised, stderr.getvalue())


def probe_startup_check():
    """startup_check blocks a finding only when its severity rank reaches the threshold
    rank, raises HonestCheckError under on_error='raise' when something blocks and prints
    nothing, prints the block to stderr under 'warn' while returning, prints and exits 1
    under 'halt', returns on a clean run whatever on_error is, and raises a message-bearing
    HonestCheckError on an on_error word in no branch."""
    try:
        from honest_check import startup_check
    except ImportError as exc:
        return [f"cannot import startup_check: {exc}"]

    bad = []
    with tempfile.TemporaryDirectory() as directory:
        # Part 1: the severity threshold, as a 3x3 matrix read under on_error='raise'.
        for severity, threshold, should_raise in _THRESHOLD_MATRIX:
            path = _write(directory, _SOURCE_BY_SEVERITY[severity])
            kind, payload, _ = _call(startup_check, path, "raise", threshold)
            raised = kind == "error" and type(payload).__name__ == "HonestCheckError"
            if should_raise and not raised:
                bad.append(
                    f"{severity} finding, threshold {threshold!r}: expected a blocking "
                    f"HonestCheckError, got {kind} {payload!r}"
                )
            if not should_raise and kind != "return":
                bad.append(
                    f"{severity} finding, threshold {threshold!r}: expected no block and a "
                    f"returned list, got {kind} {payload!r}"
                )

        # Part 2: the outcome each on_error word selects, over a two-error source.
        two = _write(directory, _TWO_ERRORS)

        kind, payload, stderr = _call(startup_check, two, "warn", "error")
        if kind != "return":
            bad.append(f"on_error 'warn': expected a returned list, got {kind} {payload!r}")
        elif not isinstance(payload, list) or len(payload) != 2:
            bad.append(f"on_error 'warn': expected two diagnostics returned, got {payload!r}")
        pointed = [line for line in stderr.strip().split("\n") if "HC-P003" in line]
        if len(pointed) != 2:
            bad.append(
                f"on_error 'warn': expected two stderr lines each naming HC-P003, got "
                f"{stderr!r}"
            )

        kind, payload, stderr = _call(startup_check, two, "raise", "error")
        if kind != "error" or type(payload).__name__ != "HonestCheckError":
            bad.append(f"on_error 'raise': expected HonestCheckError, got {kind} {payload!r}")
        elif "HC-P003" not in str(payload):
            bad.append(f"on_error 'raise': HonestCheckError message drops HC-P003: {str(payload)!r}")
        if stderr != "":
            bad.append(f"on_error 'raise': expected no stderr write, got {stderr!r}")

        kind, payload, stderr = _call(startup_check, two, "halt", "error")
        if kind != "exit":
            bad.append(f"on_error 'halt': expected SystemExit, got {kind} {payload!r}")
        elif payload != 1:
            bad.append(f"on_error 'halt': expected exit code 1, got {payload!r}")
        if "HC-P003" not in stderr:
            bad.append(f"on_error 'halt': expected the block printed to stderr, got {stderr!r}")

        # Part 3: a clean run returns under every on_error word, even 'raise'.
        clean = _write(directory, _CLEAN)
        kind, payload, _ = _call(startup_check, clean, "raise", "error")
        if kind != "return" or payload != []:
            bad.append(
                f"clean run, on_error 'raise': expected an empty returned list, got "
                f"{kind} {payload!r}"
            )

        # Part 3: an on_error word in no branch raises a message-bearing HonestCheckError.
        kind, payload, _ = _call(startup_check, clean, "bogus", "error")
        if kind != "error" or type(payload).__name__ != "HonestCheckError":
            bad.append(f"on_error 'bogus': expected HonestCheckError, got {kind} {payload!r}")
        elif "bogus" not in str(payload):
            bad.append(f"on_error 'bogus': message does not name the word: {str(payload)!r}")

    return bad
