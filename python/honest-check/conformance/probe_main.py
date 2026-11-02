"""main is the command-line door: it hands argv to run_check and yields the exit code.

The in-process cases pin main itself: a clean .py yields 0, a class .py yields 1, and a
routed declaration-read Fault is discharged as a HonestCheckError carrying the Fault's
problem and remedy (the one place a Fault crosses from a value into a world effect,
§HC-R002).

The subprocess cases pin the __main__ shim that wraps main, which only runs when cli.py is
executed as a script. They run the real file and read the process exit code and stderr: a
clean tree exits 0, a class tree exits 1, and a missing --declaration exits 2 after the door
prints the Fault to stderr. A last case imports the module as a plain import and checks it
produces no output, so the __main__ guard cannot be dropped without the door firing on every
import.

Real temp trees; stdout captured; cwd set to the temp dir so no stray honest-check.toml
ancestor changes the adoption level, restored in finally.
"""

import contextlib
import io
import os
import subprocess
import sys
import tempfile

_CASES = [
    {"source": "x = 1\n", "expect": 0},
    {"source": "class Report:\n    pass\n", "expect": 1},
]


def _cli_path():
    """The absolute path of cli.py, so the subprocess cases run the real door as a script."""
    import honest_check.cli

    return honest_check.cli.__file__


def _run_script(args):
    """Run cli.py as a script under the same interpreter, returning (code, stdout, stderr)."""
    completed = subprocess.run(
        [sys.executable, _cli_path(), *args],
        capture_output=True,
        text=True,
    )
    return completed.returncode, completed.stdout, completed.stderr


def probe_main():
    try:
        from honest_check import main
    except ImportError as exc:
        return [f"cannot import main: {exc}"]

    bad = []
    start = os.getcwd()
    for case in _CASES:
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "source.py"), "w", encoding="utf-8") as fh:
                fh.write(case["source"])
            buf = io.StringIO()
            try:
                os.chdir(d)
                with contextlib.redirect_stdout(buf):
                    got = main([d])
            finally:
                os.chdir(start)
            try:
                code = int(got)
            except (ValueError, TypeError):
                bad.append(
                    f"main over {case['source']!r} -> {got!r}, "
                    f"not an exit code; expected {case['expect']}"
                )
                continue
            if code != case["expect"]:
                bad.append(
                    f"main over {case['source']!r} -> {code}, expected {case['expect']}"
                )

    # When run_check routes a declaration-read Fault outward, the door discharges it as
    # a HonestCheckError carrying the Fault's problem and remedy.
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "m.py"), "w", encoding="utf-8") as fh:
            fh.write("def present(x):\n    return x\n")
        buf = io.StringIO()
        raised = None
        try:
            os.chdir(d)
            with contextlib.redirect_stdout(buf):
                main(["--declaration", os.path.join(d, "missing.hd"), d])
        except Exception as exc:
            raised = exc
        finally:
            os.chdir(start)
        if raised is None:
            bad.append("main with a missing --declaration did not raise; expected HonestCheckError")
        elif type(raised).__name__ != "HonestCheckError":
            bad.append(
                f"main with a missing --declaration raised {type(raised).__name__}, "
                f"expected HonestCheckError"
            )
        elif "declaration" not in str(raised):
            bad.append(
                f"main with a missing --declaration raised a message that drops the Fault "
                f"text: {str(raised)!r}"
            )

    # The __main__ shim, run as a script. A clean tree exits 0, a class tree exits 1.
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "s.py"), "w", encoding="utf-8") as fh:
            fh.write("x = 1\n")
        code, _, _ = _run_script([d])
        if code != 0:
            bad.append(f"cli.py as a script over a clean tree exited {code}, expected 0")

    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "s.py"), "w", encoding="utf-8") as fh:
            fh.write("class Report:\n    pass\n")
        code, _, _ = _run_script([d])
        if code != 1:
            bad.append(f"cli.py as a script over a class tree exited {code}, expected 1")

    # A missing --declaration: the shim discharges the Fault at exit 2 after printing it.
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "s.py"), "w", encoding="utf-8") as fh:
            fh.write("x = 1\n")
        code, _, stderr = _run_script(["--declaration", os.path.join(d, "missing.hd"), d])
        if code != 2:
            bad.append(f"cli.py as a script over a missing --declaration exited {code}, expected 2")
        if stderr.strip() == "":
            bad.append("cli.py as a script over a missing --declaration printed nothing to stderr")

    # A plain import runs the door nowhere: no stdout, exit 0. If the __main__ guard were
    # dropped, importing would run main over the interpreter's own argv and print a report.
    imported = subprocess.run(
        [sys.executable, "-c", "import honest_check.cli"],
        capture_output=True,
        text=True,
    )
    if imported.returncode != 0:
        bad.append(f"importing honest_check.cli exited {imported.returncode}, expected 0")
    if imported.stdout != "":
        bad.append(f"importing honest_check.cli wrote to stdout: {imported.stdout!r}")

    return bad
