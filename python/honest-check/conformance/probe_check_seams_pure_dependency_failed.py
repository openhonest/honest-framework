# scenario: check_seams rejects a failed pure call as manifest dependency evidence
# inherits: hd=python/honest-check/honest-check.hd::check_seams -> feature=specs/features/honest-check.feature::check_seams rejects a failed pure call as manifest dependency evidence
"""A pure call to a boundary fails and cannot cover the manifest dependency."""

_DECLARATIONS = [
    'module owner\n  fn build : () -> int pure_call "world.read" note "requests an answer"\n',
    'module world\n  boundary_in fn read : () -> int side_effect reads "file:data" note "reads data"\n',
]
_PATHS = {"owner": "packages/owner/owner.hd", "world": "packages/world/world.hd"}
_EXPECTED = [("HC-REF007", "error", _PATHS["owner"]), ("HC-REF012", "error", _PATHS["owner"])]


def probe_check_seams_pure_dependency_failed():
    """Report the wrong role and the uncovered dependency at the caller."""
    from honest_check import check_seams
    from honest_design import read_hd

    modules = [read_hd(source)["ok"]["modules"][0] for source in _DECLARATIONS]
    got = check_seams(
        declarations={module["name"]: module for module in modules},
        paths=_PATHS,
        manifest_deps={"owner": ["world"]},
        in_scope=["owner"],
    )
    findings = sorted(
        (finding["rule_id"], finding["severity"], finding["source_location"])
        for finding in got
    )
    if findings != _EXPECTED:
        return [f"check_seams returned {findings!r}, expected {_EXPECTED!r}"]
    return []
