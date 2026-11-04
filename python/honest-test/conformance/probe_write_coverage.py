"""Conformance fragment for the write_coverage scenario (honest-test.feature ~line 113).

Scenario: write_coverage writes the report's coverage as coverage.json.
  Then it writes the report's CoverageReport field as coverage.json, the file
  honest-check reads for HC-P009 and other cross-tool checks.
  And it returns nothing and makes no decision, since the coverage numbers are
  already measured.
  And its one side effect is writing the file.

write_coverage is a boundary_out sink, so the honest test asserts the REAL effect:
it writes a file. The signature takes only `report` (no path), so the sink writes
coverage.json in the current working directory. The probe chdir's into a fresh
temp dir (saving and restoring the original cwd), builds a RunReport dict carrying
a CoverageReport in its `coverage` field, calls the real
`from honest_test import write_coverage`, then reads coverage.json back and asserts
its parsed JSON carries the CoverageReport's version and its vocabularies dimension.

The function is imported real: no mock of open or json. The spec §9.5 example and
the .hd CoverageReport type disagree on the per-dimension field names and on a
`timestamp` field; the .hd leads and the scenario says write_coverage "writes the
report's CoverageReport field", so the probe pins `version` and the `vocabularies`
dimension, which §9.5 and the .hd agree on, rather than the disputed shapes.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

import json
import os
import tempfile

from honest_test import write_coverage

# A populated CoverageReport (honest-test.hd: version is "1.0"; each dimension maps
# a name to a Coverage record {total, exercised, pct}).
_COVERAGE = {
    "version": "1.0",
    "vocabularies": {"format_vocab": {"total": 5, "exercised": 5, "pct": 100}},
    "chains": {"format_pipeline": {"total": 3, "exercised": 3, "pct": 100}},
    "honesty": {"format_pipeline": {"total": 3, "exercised": 3, "pct": 100}},
    "state_machines": {"order_machine": {"total": 5, "exercised": 5, "pct": 100}},
}

# The full RunReport whose `coverage` field write_coverage writes out.
_REPORT = {
    "chains": 1,
    "links": 3,
    "vocabularies": 1,
    "permutations": 3000,
    "failures": 0,
    "adversarial_rejected": 12,
    "coverage": _COVERAGE,
    "mutation_caught": 41,
    "mutation_total": 41,
}

_CASES = [
    # (a) A RunReport with a populated CoverageReport. coverage.json must exist and
    # parse to the report's CoverageReport: the version "1.0" and the vocabularies
    # dimension, written out as literals a stub (which writes no file) cannot pass.
    {
        "report": _REPORT,
        "expect_version": "1.0",
        "expect_vocabularies": {"format_vocab": {"total": 5, "exercised": 5, "pct": 100}},
        "expect_return": None,
    },
]


def probe_write_coverage():
    """write_coverage writes report.coverage to coverage.json in the cwd, and returns NOTHING."""
    bad = []
    for case in _CASES:
        report = case["report"]
        original_cwd = os.getcwd()
        workdir = tempfile.mkdtemp(prefix="hf_write_coverage_")
        try:
            os.chdir(workdir)
            returned = write_coverage(report)

            if returned is not case["expect_return"]:
                bad.append(
                    f"write_coverage(report) returned {returned!r}, "
                    f"expected {case['expect_return']!r} (NOTHING)"
                )

            path = os.path.join(workdir, "coverage.json")
            if not os.path.exists(path):
                bad.append(
                    "write_coverage(report) wrote no coverage.json in the cwd"
                )
                continue

            with open(path, encoding="utf-8") as handle:
                parsed = json.load(handle)

            if parsed.get("version") != case["expect_version"]:
                bad.append(
                    f"coverage.json version is {parsed.get('version')!r}, "
                    f"expected {case['expect_version']!r}"
                )
            if parsed.get("vocabularies") != case["expect_vocabularies"]:
                bad.append(
                    f"coverage.json vocabularies is {parsed.get('vocabularies')!r}, "
                    f"expected {case['expect_vocabularies']!r}"
                )
        finally:
            os.chdir(original_cwd)
    return bad


def run():
    bad = probe_write_coverage()
    for line in bad:
        print(line)
    print(f"probe_write_coverage: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
