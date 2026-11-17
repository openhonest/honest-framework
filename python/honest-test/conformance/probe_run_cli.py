"""RED probe for honest-test.run_cli — the CLI door (.hd, section 11).

run_cli is the door the host starts with `python -m honest_test [src_dir]`. It hands
src_dir to run_suite, which drives the whole run, and returns what run_suite
returned: the assembled RunReport on a completed run, or the Fault run_suite passed
outward when the module source could not be parsed for mutation. It raises nothing —
a run that could not complete comes back as a Fault for the host to turn into a
non-zero exit. The probe runs it over a real temporary source directory from a
temporary working directory (so the stdout report and coverage.json land in the
temp dir), then cleans up. honest-test has no code yet, so importing honest_test
fails — the correct red state.
"""

import os
import shutil
import tempfile

from honest_test import run_cli

_REPORT_FIELDS = ("chains", "links", "vocabularies", "failures")


def _is_fault(value):
    """honest-test's own Fault carries problem and remedy (.hd Fault type)."""
    return isinstance(value, dict) and "problem" in value and "remedy" in value


def _is_run_report(value):
    return isinstance(value, dict) and all(field in value for field in _REPORT_FIELDS)


def probe_run_cli():
    """run_cli returns a dict that is either a RunReport or a Fault, and raises
    nothing, when driven over a clean source directory."""
    bad = []

    src_dir = tempfile.mkdtemp()
    work_dir = tempfile.mkdtemp()
    saved_cwd = os.getcwd()
    try:
        module = (
            '"""A clean module under test with no honest declarations."""\n'
            "\n"
            "def helper(x):\n"
            "    return x\n"
        )
        with open(os.path.join(src_dir, "undertest_mod.py"), "w", encoding="utf-8") as f:
            f.write(module)

        os.chdir(work_dir)  # contain the stdout report and coverage.json write
        try:
            got = run_cli(src_dir)
        except Exception as e:  # noqa: BLE001
            bad.append(f"run_cli raised instead of returning a RunReport or a Fault: {e!r}")
            return bad

        if _is_fault(got):
            pass  # a Fault is a legal arm of the union
        elif _is_run_report(got):
            pass  # a completed run yields a RunReport
        else:
            bad.append(
                f"run_cli returned {got!r}, expected a RunReport (with {_REPORT_FIELDS}) "
                "or a honest-test Fault (problem, remedy)"
            )
    finally:
        os.chdir(saved_cwd)
        shutil.rmtree(src_dir)
        shutil.rmtree(work_dir)

    return bad


def run():
    failures = probe_run_cli()
    for message in failures:
        print(f"FAIL run_cli: {message}")
    print(f"run_cli probe: {'PASS' if not failures else str(len(failures)) + ' failed'}")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)
