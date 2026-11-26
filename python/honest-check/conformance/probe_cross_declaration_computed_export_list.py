# scenario: cross_declaration reports a supplied initializer with a computed export list
# inherits: hd=python/honest-check/honest-check.hd::cross_declaration -> feature=specs/features/honest-check.feature::cross_declaration reports a supplied initializer with a computed export list

from honest_check import cross_declaration
from honest_design import read_hd

_EXPORT_SOURCE = b"def run():\n    return 1\n\ndef projected_exports():\n    return ['run']\n\n__all__ = projected_exports()\n"
_DECLARATION = 'module example\n  layer correctness\n  fn run : () -> int note "run"\n  fn projected_exports : () -> list<str> note "returns export names"\n'


def probe_cross_declaration_computed_export_list():
    declaration = read_hd(_DECLARATION)["ok"]["modules"][0]
    other_module = {"path": "src/example/worker.py", "text": b"CONSTANT = 1\n"}
    decoy_initializer = {"path": "src/example/other/__init__.py", "text": b"__all__ = []\n"}
    real_path = "src/example/__init__.py"
    failures = []
    cases = [
        (_EXPORT_SOURCE, [("HC-REF005", "error", real_path, True)]),
        (b"__all__ = []\n", []),
    ]
    for export_source, expected in cases:
        sources = [
            other_module,
            decoy_initializer,
            {"path": real_path, "text": export_source},
        ]
        findings = cross_declaration(sources, declaration, export_source, ["HC-REF005"])
        observed = [
            (
                item["rule_id"], item["severity"], item["source_location"],
                "literal export list" in item["message"].casefold(),
            )
            for item in findings
        ]
        if observed != expected:
            failures.append(f"Expected {expected!r} for initializer {export_source!r}, got {findings!r}")
    return failures
