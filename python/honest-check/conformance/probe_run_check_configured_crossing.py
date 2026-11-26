# scenario: run_check completes configured declaration crossing
# inherits: hd=python/honest-check/honest-check.hd::run_check -> feature=specs/features/honest-check.feature::run_check completes configured declaration crossing
"""run_check crosses configured files and returns the report's exit code."""

import contextlib
import io
import json
import tempfile
from pathlib import Path

_DECLARATION = (
    "module demo\n\n  layer correctness\n\n"
    '  fn handle : () -> int note "returns one synchronously"\n'
)
_SOURCE = "async def handle():\n    return 1\n\ndef extra():\n    return 2\n"
_CASES = [
    {
        "rule": "HC-REF005",
        "exports": 'from .worker import handle\n\n__all__ = ["handle"]\n',
        "exit_code": "0",
        "diagnostics": [],
    },
    {
        "rule": "HC-R003",
        "exports": "",
        "exit_code": "1",
        "diagnostics": [("HC-R003", "error", 1)],
    },
    {
        "rule": "HC-REF005",
        "exports": 'from .worker import extra\n\n__all__ = ["extra"]\n',
        "exit_code": "1",
        "diagnostics": [("HC-REF005", "error", 4)],
    },
]


def probe_run_check_configured_crossing():
    """Read the configured declaration and exports, apply the selected rule, and report."""
    from honest_check import run_check

    failures = []
    for case in _CASES:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            declaration = root / "demo.hd"
            declaration.write_text(_DECLARATION)
            (root / "worker.py").write_text(_SOURCE)
            argv = [
                str(root),
                "--declaration", str(declaration),
                "--format", "json",
                "--severity", "error",
                "--rule", case["rule"],
            ]
            if case["exports"]:
                export_file = root / "__init__.py"
                export_file.write_text(case["exports"])
                argv.extend(["--exports", str(export_file)])
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = run_check(argv)
            if exit_code != case["exit_code"]:
                failures.append(
                    f"run_check with {case['rule']} and exports {case['exports']!r} "
                    f"returned {exit_code!r}, expected {case['exit_code']!r}"
                )
            try:
                report = json.loads(stdout.getvalue())
            except json.JSONDecodeError:
                failures.append(
                    f"run_check with {case['rule']} did not write a JSON report: {stdout.getvalue()!r}"
                )
                continue
            diagnostics = [
                (item["rule"], item["severity"], item["line"])
                for item in report["diagnostics"]
            ]
            if diagnostics != case["diagnostics"]:
                failures.append(
                    f"run_check with {case['rule']} and exports {case['exports']!r} "
                    f"reported {diagnostics!r}, expected {case['diagnostics']!r}"
                )
    return failures
