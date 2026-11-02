"""run_check orchestrates the whole CLI path and returns the exit code.

A directory holding a class .py fails the gate: int(run_check([dir])) == 1. A clean
.py passes: int(run_check([dir])) == 0. Real temp tree; stdout is captured so the
rendered report stays quiet; cwd is set to the temp dir so no stray honest-check.toml
ancestor changes the adoption level, and restored in finally.
"""

import contextlib
import io
import os
import tempfile

_CASES = [
    {"source": "class Report:\n    pass\n", "expect": 1},
    {"source": "x = 1\n", "expect": 0},
]


def probe_run_check():
    try:
        from honest_check import run_check
    except ImportError as exc:
        return [f"cannot import run_check: {exc}"]

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
                    got = run_check([d])
            finally:
                os.chdir(start)
            try:
                code = int(got)
            except (ValueError, TypeError):
                bad.append(
                    f"run_check over {case['source']!r} -> {got!r}, "
                    f"not an exit code; expected {case['expect']}"
                )
                continue
            if code != case["expect"]:
                bad.append(
                    f"run_check over {case['source']!r} -> {code}, expected {case['expect']}"
                )

    # Crossing mode with a --declaration that names no readable file: run_check routes
    # the read Fault straight outward as its own answer, checking nothing (§HC-R002).
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "m.py"), "w", encoding="utf-8") as fh:
            fh.write("def present(x):\n    return x\n")
        buf = io.StringIO()
        try:
            os.chdir(d)
            with contextlib.redirect_stdout(buf):
                got = run_check(["--declaration", os.path.join(d, "missing.hd"), d])
        finally:
            os.chdir(start)
        if not (isinstance(got, dict) and "problem" in got):
            bad.append(
                f"run_check crossing a missing .hd -> {got!r}, expected a Fault with 'problem'"
            )

    # Crossing mode with a valid --declaration and --exports that agree with the code:
    # cross_declaration finds nothing, so the run exits 0.
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "m.py"), "w", encoding="utf-8") as fh:
            fh.write("def clean_fn(x):\n    return x\n")
        hd = os.path.join(d, "m.hd")
        with open(hd, "w", encoding="utf-8") as fh:
            fh.write("module m\n\n  fn clean_fn : (x: str) -> str\n")
        exports = os.path.join(d, "exports.py")
        with open(exports, "w", encoding="utf-8") as fh:
            fh.write('__all__ = ["clean_fn"]\n')
        buf = io.StringIO()
        try:
            os.chdir(d)
            with contextlib.redirect_stdout(buf):
                got = run_check(
                    ["--declaration", hd, "--exports", exports, "--rule", "HC-REF005", d]
                )
        finally:
            os.chdir(start)
        if int(got) != 0:
            bad.append(
                f"run_check crossing an agreeing .hd -> {got!r}, expected exit 0"
            )

    # Base mode where a honest-<name>/honest-<name>.hd governs the file, alongside a
    # non-code (.css) file the role and auth passes skip: the class still fails the gate.
    with tempfile.TemporaryDirectory() as d:
        mod = os.path.join(d, "honest-foo")
        os.mkdir(mod)
        with open(os.path.join(mod, "honest-foo.hd"), "w", encoding="utf-8") as fh:
            fh.write("module honest-foo\n\n  fn noop : (x: str) -> str\n")
        with open(os.path.join(mod, "x.py"), "w", encoding="utf-8") as fh:
            fh.write("class Report:\n    pass\n")
        with open(os.path.join(mod, "style.css"), "w", encoding="utf-8") as fh:
            fh.write(".a { color: red; }\n")
        buf = io.StringIO()
        try:
            os.chdir(d)
            with contextlib.redirect_stdout(buf):
                got = run_check([d])
        finally:
            os.chdir(start)
        out = buf.getvalue()
        if int(got) != 1:
            bad.append(f"run_check base mode under a module .hd -> {got!r}, expected exit 1")
        if "HC-P003" not in out:
            bad.append(f"run_check base mode under a module .hd is missing HC-P003; got {out!r}")
    return bad
