# scenario: cross_declaration preserves arity findings when the export list is invalid
# inherits: hd=python/honest-check/honest-check.hd::cross_declaration -> feature=specs/features/honest-check.feature::cross_declaration preserves arity findings when the export list is invalid

from honest_check import cross_declaration
from honest_design import read_hd


def probe_cross_declaration_invalid_export_arity():
    declaration = read_hd(
        'module example\n  layer correctness\n  fn combine : (left: int) -> int note "combines values"\n'
    )["ok"]["modules"][0]
    export_source = b'__all__ = list(("undeclared",))\n'
    sources = [
        {"path": "src/example/__init__.py", "text": export_source},
        {"path": "src/example/worker.py", "text": b"def combine(left, right): return left + right\n"},
    ]
    findings = cross_declaration(sources, declaration, export_source, ["HC-REF005"])
    actual = sorted(
        (item["rule_id"], item["severity"],
         "literal export list" in item["message"].casefold(),
         "combine" in item["message"] and "1" in item["message"] and "2" in item["message"])
        for item in findings
    )
    expected = [("HC-REF005", "error", False, True), ("HC-REF005", "error", True, False)]
    if actual != expected:
        return [f"Expected the invalid export and independent combine arity errors, got {findings!r}"]
    return []
