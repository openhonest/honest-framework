"""main is the command-line door: it hands argv to run_check and yields the exit code.

A directory holding a clean .py yields success: int(main([dir])) == 0. A directory
holding a class .py yields the gate failure the scenario fixes: int(main([dir])) == 1
(scenario: '1 means the gate failed with one or more errors'). The class case is here
so a stub that returns 0 cannot pass. Real temp tree; stdout captured; cwd set to the
temp dir so no stray honest-check.toml ancestor changes the adoption level, restored
in finally.
"""

import contextlib
import io
import os
import tempfile

_CASES = [
    {"source": "x = 1\n", "expect": 0},
    {"source": "class Report:\n    pass\n", "expect": 1},
]


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
    return bad
