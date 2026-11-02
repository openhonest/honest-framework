"""honest-check conformance runner (section 9.2).

The test-of-record for honest-check is data, not hand-coded tests. Two parts run
here:

  - suite.json: one case per rule category. A case gives a source string and the
    diagnostics check_source must produce over it (rule, severity, line). The
    runner feeds each case's source to check_source and compares the triples
    (rule_id, severity, line) it got against the triples the case expects. The
    comparison is exact: a case that expects one diagnostic fails if the checker
    also produces a second, so a false positive is caught as loudly as a missed
    finding. The per-rule behaviour the rule engine folds over the graph is
    pinned here, not by a function scenario (the engine is data inside
    check_source).

  - probe_*.py: the honest tests derived one-per-function from the feature
    scenarios. Each is a function returning a list of failure strings, empty
    when the function under test behaves. The runner discovers every probe_*.py
    beside it, calls its like-named function, and folds the failures in.

  uv run --package honest-check python honest-check/conformance/run_conformance.py
"""

import importlib
import json
import sys
from pathlib import Path

from honest_check import check_source

# The extension carries the grammar: honest-parse detects the language from the
# path's suffix, so a case names its language and the runner hands check_source a
# path with the matching extension. A closed table with a no-match row, because a
# case naming a language with no extension here is a suite error, not a default.
_EXTENSION_BY_LANGUAGE = {
    "python": ".py",
    "javascript": ".js",
    "ruby": ".rb",
    "go": ".go",
}


def _path_for(case):
    """The synthetic path a case's source is checked under, carrying the
    extension that selects its grammar. Returns None on a language the table
    does not carry rather than guessing a grammar."""
    language = case["input"]["language"]
    if language not in _EXTENSION_BY_LANGUAGE:
        return None
    return f"case_{case['id']}{_EXTENSION_BY_LANGUAGE[language]}"


def _line_of(source_location):
    """The 1-based line a diagnostic sits on, read from its 'file:line:col'
    source_location. A location that carries no line (the bare path form) reads
    as None, which a case may expect by omitting the line field."""
    parts = source_location.rsplit(":", 2)
    if len(parts) != 3:
        return None
    if not parts[1].isdigit():
        return None
    return int(parts[1])


def _triples_got(diagnostics):
    """The (rule, severity, line) triples a run produced, sorted for comparison."""
    return sorted(
        (d["rule_id"], d["severity"], _line_of(d["source_location"]))
        for d in diagnostics
    )


def _triples_expected(case):
    """The (rule, severity, line) triples a case expects, sorted. A case that
    omits a diagnostic's line expects None there, matching a location with no
    line."""
    return sorted(
        (d["rule"], d["severity"], d.get("line"))
        for d in case["expected"]["diagnostics"]
    )


def _check_case(case):
    """Run one suite case through check_source and compare triples exactly."""
    path = _path_for(case)
    if path is None:
        return False, f"suite names unknown language {case['input']['language']!r}"
    got = check_source(case["input"]["source"], path, {}, None)
    got_triples = _triples_got(got)
    want_triples = _triples_expected(case)
    if got_triples == want_triples:
        return True, ""
    return False, f"got {got_triples}, expected {want_triples}"


def run_suite(suite_path):
    """Every suite case, exact-match on diagnostic triples."""
    suite = json.loads(Path(suite_path).read_text(encoding="utf-8"))
    passed = 0
    failed = 0
    for case in suite["cases"]:
        ok, detail = _check_case(case)
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL {case['id']} [{case['category']}]: {detail}")
    print(f"suite: {passed} passed, {failed} failed, {passed + failed} total")
    return 0 if failed == 0 else 1


def run_probes():
    """Every probe_*.py beside this runner, each a function of its own name."""
    here = Path(__file__).parent
    failed = 0
    passed = 0
    for probe_file in sorted(here.glob("probe_*.py")):
        name = probe_file.stem
        module = importlib.import_module(name)
        failures = getattr(module, name)()
        if failures:
            failed += 1
            for line in failures:
                print(f"FAIL {name}: {line}")
        else:
            passed += 1
    print(f"probes: {passed} passed, {failed} failed, {passed + failed} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    default = str(Path(__file__).parent / "suite.json")
    suite_status = run_suite(sys.argv[1] if len(sys.argv) > 1 else default)
    probe_status = run_probes()
    raise SystemExit(suite_status or probe_status)
