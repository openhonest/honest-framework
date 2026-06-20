"""Conformance runner (section 9.2).

The conformance suite is the test-of-record: each case is *data* — source code as a
string plus the diagnostics it must produce. This runner feeds every case's source to
the real `check_source` and checks the expected diagnostics fire. No per-rule hand-coded
test functions: the cases are data, the runner is one generic harness.

  uv run --package honest-check python honest-check/conformance/run_conformance.py

Exit 0 if every case passes, 1 otherwise.
"""

import json
import sys
from pathlib import Path

from honest_check import check_source


def _triples(diagnostics):
    return [{"rule": d["rule"], "severity": d["severity"], "line": d["line"]} for d in diagnostics]


def _present(expected, actual):
    return any(
        a["rule"] == expected["rule"]
        and a["severity"] == expected["severity"]
        and a["line"] == expected["line"]
        for a in actual
    )


def _case_passes(expected, actual):
    # A "clean" case (no expected diagnostics) must produce no error or warning.
    if not expected:
        return not any(a["severity"] in ("error", "warning") for a in actual)
    return all(_present(e, actual) for e in expected)


def run(suite_path):
    suite = json.loads(Path(suite_path).read_text(encoding="utf-8"))
    passed = 0
    failed = 0
    for case in suite["cases"]:
        actual = _triples(check_source(case["input"]["source"], case["id"]))
        expected = case["expected"]["diagnostics"]
        if _case_passes(expected, actual):
            passed += 1
        else:
            failed += 1
            print(f"FAIL {case['id']} ({case.get('category','')}):")
            print(f"     expected: {expected}")
            print(f"     actual:   {actual}")
    print(f"conformance: {passed} passed, {failed} failed, {passed + failed} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import laws_hc
    import laws_hc_rules

    default = str(Path(__file__).parent / "suite.json")
    suite_status = run(sys.argv[1] if len(sys.argv) > 1 else default)
    laws_status = laws_hc.run()
    rules_status = laws_hc_rules.run()
    raise SystemExit(suite_status or laws_status or rules_status)
