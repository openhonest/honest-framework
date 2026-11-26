# scenario: cross_declaration uses a synthetic label for an invalid initializer without a known path
# inherits: hd=python/honest-check/honest-check.hd::cross_declaration -> feature=specs/features/honest-check.feature::cross_declaration uses a synthetic label for an invalid initializer without a known path

from honest_check import cross_declaration
from honest_design import read_hd


def probe_cross_declaration_synthetic_export_location():
    declaration = read_hd("module example\n  layer correctness\n")["ok"]["modules"][0]
    findings = cross_declaration([], declaration, b"__all__ = tuple()\n", ["HC-REF005"])
    actual = [
        (item["rule_id"], item["severity"], item["source_location"],
         "literal export list" in item["message"].casefold())
        for item in findings
    ]
    expected = [("HC-REF005", "error", "__init__.py", True)]
    if actual != expected:
        return [f"Expected one invalid export error at the synthetic label, got {findings!r}"]
    return []
