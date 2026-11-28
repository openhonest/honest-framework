# scenario: check_ref012
# inherits: hd=python/honest-check/honest-check.hd::check_ref012 -> feature=specs/features/honest-check.feature::check_ref012 needs no honest-parse deferral once honest-parse publishes its pure functions -> test=python/honest-check/conformance/probe_check_ref012_parse_deferral.py::probe_check_ref012_parse_deferral
"""Once the parse module publishes its pure functions, a resolved pure_call onto one satisfies the manifest dependency and HC-REF012 does not fire, so no hardcoded per-module deferral is needed."""

# checklike stands in for honest-check: its manifest depends on the workspace
# module parselike (standing in for honest-parse), it declares NO side-effect
# seam onto parselike, and it couples to parselike only through a resolved
# pure_call "parselike.node_text" onto a function parselike publishes.
# parselike stands in for honest-parse: it declares node_text as a plain pure
# fn with no side effects and publishes it as a valid way in through an entry.
_DECLARATIONS = [
    'module checklike\n  fn check : () -> int pure_call "parselike.node_text" note "pure dependency onto parselike"\n',
    'module parselike\n  fn node_text : () -> int note "returns node text"\n  entry "import parselike" -> node_text\n',
]
_PATHS = {
    "checklike": "packages/checklike/checklike.hd",
    "parselike": "packages/parselike/parselike.hd",
}


def probe_check_ref012_parse_deferral():
    """No HC-REF012 for the parselike dependency: the resolved pure_call onto parselike's published node_text satisfies the manifest dependency without a side-effect seam."""
    from honest_check.seams import run_seam_rules
    from honest_design import read_hd

    modules = [read_hd(source)["ok"]["modules"][0] for source in _DECLARATIONS]
    findings = run_seam_rules(
        declarations={module["name"]: module for module in modules},
        paths=_PATHS,
        manifest_deps={"checklike": ["parselike"]},
        in_scope=["checklike"],
    )
    ref012 = [
        finding
        for finding in findings
        if finding["rule_id"] == "HC-REF012" and "parselike" in finding["message"]
    ]
    if ref012:
        return [
            f"run_seam_rules emitted HC-REF012 for the parselike dependency {ref012!r}, "
            f"expected none because the resolved pure_call onto parselike's published "
            f"node_text satisfies the manifest dependency; all findings: {findings!r}"
        ]
    return []
