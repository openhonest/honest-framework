"""Mutation-adequacy gate (honest-test section 9.6): the I/O harness around honest-test's pure engine.

For each module, mutate every source line one at a time (honest_test.enumerate_mutants) and require the
module's conformance suite to fail on each mutant. honest-test's run_mutants makes the pure caught/
survived decision; this driver supplies the one I/O step it cannot test on itself — write the mutant to
the source file, run the suite as a subprocess, restore the original. A surviving mutant must be declared
equivalent, with a reason, in the module's set-aside registry (conformance/mutants_setaside.json), keyed
by its file-qualified label; any undeclared survivor fails the gate. mutation_adequacy reports
caught + set_aside == total. This file is the boundary (subprocesses, file writes); it is not linted.
"""

import json
import subprocess
import sys
from pathlib import Path

from honest_test import enumerate_mutants, mutation_adequacy, run_mutants

ROOT = Path(__file__).resolve().parent


def _suite_passes(module):
    """Run the module's conformance suite as a subprocess; True iff it exits 0 (passes)."""
    result = subprocess.run(
        ["uv", "run", "--package", f"honest-{module}", "python", f"honest-{module}/conformance/run_conformance.py"],
        cwd=ROOT,
        capture_output=True,
    )
    return result.returncode == 0


def _src_files(module):
    """Every source file of a module, sorted."""
    return sorted((ROOT / f"honest-{module}" / "src" / f"honest_{module}").rglob("*.py"))


def _set_aside(module):
    """The module's set-aside registry {file-qualified-label: reason}, or empty when none is declared."""
    path = ROOT / f"honest-{module}" / "conformance" / "mutants_setaside.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _run_module(module):
    """Mutate every source file of a module, run the suite against each mutant, and return the adequacy
    report. Each file is mutated under a per-file closure that restores the original even on failure."""
    mutants_all, survivors_all = [], []
    for path in _src_files(module):
        source = path.read_text(encoding="utf-8")
        relpath = str(path.relative_to(ROOT))
        file_mutants = [{"operator": m["operator"], "label": f"{relpath}:{m['label']}", "source": m["source"]} for m in enumerate_mutants(source)]

        def run_suite(mutated_source, target=path, original=source):
            try:
                target.write_text(mutated_source, encoding="utf-8")
                return _suite_passes(module)
            finally:
                target.write_text(original, encoding="utf-8")

        survivors_all.extend(run_mutants(file_mutants, run_suite))
        mutants_all.extend(file_mutants)
    return mutation_adequacy(mutants_all, survivors_all, _set_aside(module))


def main(modules):
    status = 0
    for module in modules:
        report = _run_module(module)
        print(f"mutate: honest-{module} — {report['caught']} caught, {report['set_aside']} set aside, {len(report['undeclared'])} undeclared of {report['total']} mutants")
        for survivor in report["undeclared"]:
            print(f"  SURVIVED  {survivor['operator']}  {survivor['label']}")
        if not report["adequate"]:
            status = 1
    if status == 0:
        print("mutate: every mutant is caught or declared equivalent — the suite is mutation-adequate.")
    else:
        print("mutate: undeclared survivors above — add a conformance case that catches each, or declare it equivalent with a reason in conformance/mutants_setaside.json.", file=sys.stderr)
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
