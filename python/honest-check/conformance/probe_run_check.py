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
    return bad
