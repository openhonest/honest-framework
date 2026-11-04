"""Conformance fragment for the run_suite scenarios (honest-test.feature ~lines 50-78).

run_suite is the CLI run orchestrator. Its .hd note and four feature scenarios drive it:

  line 50  completed run: resolves config once, loads once, drives the core, drives BOTH
           sinks (print_report to stdout, write_coverage to coverage.json) and returns the
           assembled RunReport.
  line 59  source-text path: for each file reads, parses, finds predicates, classifies each
           and dispatches to the matching generator (enumerate_lengths for a length-bounded
           predicate), producing generated cases.
  line 66  live-value path: enumerate_sets permutes each loaded vocabulary and the honesty
           checks run each link over the loaded declarations.
  line 74  fault-return path: when the module source does not parse, run_suite returns the
           Fault mutate_source answers, passing it outward to the door rather than raising.

run_suite is an orchestrator over a real source directory, so this probe tests it as an
integration over a temp project, observing its REAL effects (the two sinks) and its return.
No mocks, no patching: it builds a tiny temp src_dir holding one module that declares a
length-bounded recognizer predicate (the source-text path) AND a live Set-based vocabulary
and link via honest_type (the live-value path), chdir's into the project so coverage.json
lands there, captures stdout, and calls the real honest_test.run_suite.

It cannot inspect internal call order from outside, so it asserts the OBSERVABLE result each
scenario names: the returned RunReport's fields and counts, the non-empty rendered report on
stdout, the parseable coverage.json, and the returned Fault on an unparseable module.

This is its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py / suite.json are untouched. Sibling agents own
probe_run_cli.py and probe_run_body_check.py; this fragment touches neither.
"""

import contextlib
import io
import json
import os
import tempfile

from honest_test import run_suite

# The good temp module: one length-bounded recognizer predicate (is_short, a len(s)
# comparison classify_predicate sorts as length_bounded, exercising the source-text path),
# one live 3-member Set vocabulary and one live link over it (exercising the live-value
# path). It imports the real honest_type, importable in the loading interpreter. It declares
# no state machine, schema, component, provider or gate.
_GOOD_MODULE = '''\
import honest_type as ht


def is_short(s):
    """A length-bounded recognizer predicate: strings of length 3 or less."""
    return len(s) <= 3


catalog = ht.vocabulary({"color": {"red", "green", "blue"}})


@ht.link(accepts=catalog, emits="rendered_cell")
def render_cell(manifest):
    return manifest
'''

# The broken temp module: Python source that does not parse (missing colon, unbalanced
# parenthesis). mutate_source must answer a Fault, which run_suite passes outward.
_BROKEN_MODULE = '''\
def is_short(s)
    return len(s <= 3
'''

# The nine RunReport fields the completed run must return (honest-test.hd type RunReport).
_REPORT_FIELDS = (
    "chains",
    "links",
    "vocabularies",
    "permutations",
    "failures",
    "adversarial_rejected",
    "coverage",
    "mutation_caught",
    "mutation_total",
)

# The four CoverageReport fields coverage.json must carry (honest-test.hd type CoverageReport).
_COVERAGE_FIELDS = ("version", "vocabularies", "chains", "honesty", "state_machines")


def _build_project(module_source):
    """A fresh temp project: a src/ dir holding one module. Returns (root, src_dir)."""
    root = tempfile.mkdtemp(prefix="probe_run_suite_")
    src_dir = os.path.join(root, "src")
    os.makedirs(src_dir)
    with open(os.path.join(src_dir, "sample_module.py"), "w") as handle:
        handle.write(module_source)
    return root, src_dir


def _run(src_dir, root):
    """Run run_suite with cwd at root (so coverage.json lands there) and stdout captured."""
    buffer = io.StringIO()
    previous = os.getcwd()
    os.chdir(root)
    try:
        with contextlib.redirect_stdout(buffer):
            result = run_suite(src_dir)
    finally:
        os.chdir(previous)
    return result, buffer.getvalue()


def probe_run_suite():
    """run_suite over a real temp project returns the assembled RunReport, writes the rendered report to stdout and a parseable coverage.json, and returns a Fault (never raises) when the module source does not parse."""
    bad = []

    # ---- completed run + source-text + live-value, over one good temp project (lines 50, 59, 66) ----
    root, src_dir = _build_project(_GOOD_MODULE)
    report = None
    stdout = ""
    try:
        report, stdout = _run(src_dir, root)
    except Exception as error:
        bad.append(
            f"completed run: run_suite over a parseable project raised "
            f"{type(error).__name__}: {error}; expected a returned RunReport"
        )

    if report is not None:
        if isinstance(report, dict) and "problem" in report:
            bad.append(
                f"completed run: run_suite returned a Fault {report!r} over parseable "
                f"source, expected a RunReport"
            )
        elif not isinstance(report, dict):
            bad.append(
                f"completed run: run_suite returned {report!r}, expected a RunReport dict"
            )
        else:
            missing = [field for field in _REPORT_FIELDS if field not in report]
            if missing:
                bad.append(
                    f"completed run: RunReport missing fields {missing}; got keys "
                    f"{sorted(report)}"
                )
            # live-value path (line 66): the one declared vocabulary was loaded and seen.
            if report.get("vocabularies") != 1:
                bad.append(
                    f"live-value path: RunReport vocabularies={report.get('vocabularies')!r}, "
                    f"expected 1 (the temp module declares exactly one vocabulary)"
                )
            # source-text + live path (lines 59, 66): a real pass over a 3-member Set
            # vocabulary plus a length-bounded predicate generated cases. A stub that runs
            # nothing yields 0; only a real generate-and-run pass yields cases.
            permutations = report.get("permutations")
            if not isinstance(permutations, int) or permutations < 3:
                bad.append(
                    f"source-text/live path: RunReport permutations={permutations!r}, "
                    f"expected >= 3 (a 3-member Set vocabulary yields at least 3 cases)"
                )

    # completed run (line 50): print_report wrote the rendered report to stdout.
    if not stdout.strip():
        bad.append(
            "completed run: print_report wrote nothing to stdout; expected the rendered report"
        )

    # completed run (line 50): write_coverage wrote a parseable coverage.json.
    coverage_path = os.path.join(root, "coverage.json")
    if not os.path.exists(coverage_path):
        bad.append(
            "completed run: write_coverage did not write coverage.json to the run directory"
        )
    else:
        coverage = None
        try:
            with open(coverage_path) as handle:
                coverage = json.load(handle)
        except Exception as error:
            bad.append(f"completed run: coverage.json did not parse as JSON: {error}")
        if coverage is not None:
            if not isinstance(coverage, dict):
                bad.append(
                    f"completed run: coverage.json is {type(coverage).__name__}, expected a "
                    f"CoverageReport object"
                )
            else:
                missing = [field for field in _COVERAGE_FIELDS if field not in coverage]
                if missing:
                    bad.append(
                        f"completed run: coverage.json missing CoverageReport fields {missing}"
                    )

    # ---- fault-return path, over an unparseable module (line 74) ----
    fault_root, fault_src = _build_project(_BROKEN_MODULE)
    try:
        fault_result, _ = _run(fault_src, fault_root)
        is_fault = (
            isinstance(fault_result, dict)
            and "problem" in fault_result
            and "remedy" in fault_result
        )
        if not is_fault:
            bad.append(
                f"fault-return path: run_suite over unparseable source returned "
                f"{fault_result!r}, expected a Fault dict with 'problem' and 'remedy'"
            )
    except Exception as error:
        bad.append(
            f"fault-return path: run_suite over unparseable source raised "
            f"{type(error).__name__}: {error}; expected a returned Fault, not a raise"
        )

    return bad


def run():
    bad = probe_run_suite()
    for line in bad:
        print(line)
    print(f"probe_run_suite: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
