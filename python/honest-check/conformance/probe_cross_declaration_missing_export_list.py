# scenario: cross_declaration reports a supplied initializer with no export list
# inherits: hd=python/honest-check/honest-check.hd::cross_declaration -> feature=specs/features/honest-check.feature::cross_declaration reports a supplied initializer with no export list

from honest_check import cross_declaration
from honest_design import read_hd

_EXPORT_SOURCE = b'def run():\n    return 1\n'
_DECLARATION = 'module example\n  layer correctness\n  fn run : () -> int note "run"\n'


def probe_cross_declaration_missing_export_list():
    declaration = read_hd(_DECLARATION)["ok"]["modules"][0]
    cases = (
        ("src/example/__init__.py", "src/example/__init__.py"),
        ("src/example/worker.py", "src/example"),
    )
    failures = []
    for source_path, expected_location in cases:
        sources = [{"path": source_path, "text": _EXPORT_SOURCE}]
        findings = cross_declaration(sources, declaration, _EXPORT_SOURCE, ["HC-REF005"])
        observed = [
            (
                item["rule_id"], item["severity"], item["source_location"],
                "literal export list" in item["message"].casefold(),
            )
            for item in findings
        ]
        expected = [("HC-REF005", "error", expected_location, True)]
        if observed != expected:
            failures.append(f"Expected {expected!r} for source {source_path!r}, got {findings!r}")
    return failures
