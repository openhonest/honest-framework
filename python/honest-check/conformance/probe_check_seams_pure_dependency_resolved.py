# scenario: check_seams accepts a resolved pure call as manifest dependency evidence
# inherits: hd=python/honest-check/honest-check.hd::check_seams -> feature=specs/features/honest-check.feature::check_seams accepts a resolved pure call as manifest dependency evidence
"""A sibling logical module's pure call covers the owner's manifest dependency."""

_DECLARATIONS = [
    'module owner\n  fn start : () -> int note "returns one"\n',
    'module sibling\n  fn build : () -> int pure_call "utils.answer" note "reads the pure answer"\n',
    'module utils\n  fn answer : () -> int note "returns one"\n',
]
_PATHS = {
    "owner": "packages/owner/owner.hd",
    "sibling": "packages/owner/sibling.hd",
    "utils": "packages/utils/utils.hd",
}


def probe_check_seams_pure_dependency_resolved():
    """Resolve sibling evidence against the complete declaration set."""
    from honest_check import check_seams
    from honest_design import read_hd

    modules = [read_hd(source)["ok"]["modules"][0] for source in _DECLARATIONS]
    got = check_seams(
        declarations={module["name"]: module for module in modules},
        paths=_PATHS,
        manifest_deps={"owner": ["utils"]},
        in_scope=["owner"],
    )
    findings = [finding for finding in got if finding["rule_id"] == "HC-REF012"]
    if findings:
        return [f"check_seams returned {findings!r}, expected sibling evidence to cover utils"]
    return []
