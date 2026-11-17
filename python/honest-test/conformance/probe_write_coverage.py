"""honest-test conformance: write_coverage, the coverage.json sink.

write_coverage writes the report's CoverageReport as coverage.json, the file
honest-check reads for HC-P009 and other cross-tool checks, making no decision
because the numbers are already measured (.hd write_coverage note; spec §9.5;
feature "write_coverage writes the report's coverage as coverage.json"). Its one
observable effect is the written file, so this probe writes from a throwaway
working directory and reads coverage.json back.

No classes, no mocks. The RunReport is a real dict; the function called is the real
honest_test.write_coverage; the effect is read back from the real filesystem.
"""

import json
import os
import tempfile

from honest_test import write_coverage


def _report():
    return {
        "chains": 1,
        "links": 3,
        "vocabularies": 1,
        "permutations": 3000,
        "failures": 0,
        "adversarial_rejected": 847,
        "coverage": {
            "version": "1.0",
            "vocabularies": {"format_vocab": {"total": 5, "exercised": 5, "pct": 100}},
            "chains": {"format_pipeline": {"total": 3, "exercised": 3, "pct": 100}},
            "honesty": {"format_pipeline": {"total": 3, "exercised": 3, "pct": 100}},
            "state_machines": {},
        },
        "mutation_caught": 40,
        "mutation_total": 40,
    }


def probe_write_coverage():
    """The written coverage.json parses as JSON, stamps the format version, and
    carries the four coverage dimensions with the named vocabulary and its
    percentage, so honest-check can read the measured coverage back."""
    bad = []
    report = _report()

    with tempfile.TemporaryDirectory() as work:
        start = os.getcwd()
        os.chdir(work)
        try:
            write_coverage(report)
            path = os.path.join(work, "coverage.json")
            if not os.path.exists(path):
                bad.append("write_coverage should write coverage.json to the working directory")
                return bad
            with open(path) as handle:
                raw = handle.read()
        finally:
            os.chdir(start)

    try:
        written = json.loads(raw)
    except ValueError as error:
        bad.append(f"coverage.json should be valid JSON: {error}")
        return bad

    if written.get("version") != "1.0":
        bad.append(f"coverage.json should stamp the format version 1.0, got {written.get('version')!r}")
    for dimension in ("vocabularies", "chains", "honesty", "state_machines"):
        if dimension not in written:
            bad.append(f"coverage.json should carry the {dimension} dimension: {written}")

    vocab = written.get("vocabularies", {}).get("format_vocab")
    if not isinstance(vocab, dict):
        bad.append(f"coverage.json should carry the named vocabulary format_vocab: {written.get('vocabularies')}")
    elif vocab.get("pct") != 100:
        bad.append(f"the vocabulary coverage should report its percentage, got {vocab}")

    return bad


def run():
    messages = probe_write_coverage()
    for message in messages:
        print(f"FAIL probe_write_coverage: {message}")
    print(f"probe_write_coverage: {'PASS' if not messages else str(len(messages)) + ' failed'}")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
