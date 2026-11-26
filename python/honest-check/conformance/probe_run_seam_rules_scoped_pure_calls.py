# scenario: run_seam_rules checks scoped pure calls alongside I/O seams
# inherits: hd=python/honest-check/honest-check.hd::run_seam_rules -> feature=specs/features/honest-check.feature::run_seam_rules checks scoped pure calls alongside I/O seams
"""Resolve targets across the workspace while reporting only scoped callers."""

_DECLARATIONS = [
    'module caller\n  reader fn load : () -> int side_effect reads "store.missing"'
    ' pure_call "utils.answer" pure_call "world.read" note "loads an answer"\n',
    'module utils\n  fn answer : () -> int note "returns one"\n',
    'module world\n  boundary_in fn read : () -> int side_effect reads "file:data" note "reads data"\n',
    'module store\n  boundary_in fn read : () -> int side_effect reads "file:data"'
    ' pure_call "absent.answer" note "reads data"\n',
]
_PATHS = {
    "caller": "packages/caller/caller.hd",
    "utils": "packages/utils/utils.hd",
    "world": "packages/world/world.hd",
    "store": "packages/store/store.hd",
}
_EXPECTED = [
    ("HC-REF006", "error", _PATHS["caller"], True),
    ("HC-REF007", "error", _PATHS["caller"], True),
    ("HC-REF012", "error", _PATHS["caller"], True),
]
_NAMES = {"HC-REF006": ("store", "missing"), "HC-REF007": ("load", "world.read"), "HC-REF012": ("world",)}


def probe_run_seam_rules_scoped_pure_calls():
    """Check that scoped reporting keeps I/O, pure-role, and dependency findings."""
    from honest_check.seams import run_seam_rules
    from honest_design import read_hd

    modules = [read_hd(source)["ok"]["modules"][0] for source in _DECLARATIONS]
    findings = run_seam_rules(
        declarations={module["name"]: module for module in modules},
        paths=_PATHS,
        manifest_deps={"caller": ["utils", "world"]},
        in_scope=["caller"],
    )
    got = sorted(
        (
            finding["rule_id"],
            finding["severity"],
            finding["source_location"],
            all(name in finding["message"] for name in _NAMES.get(finding["rule_id"], ())),
        )
        for finding in findings
    )
    if got != _EXPECTED:
        return [f"run_seam_rules returned {got!r}, expected {_EXPECTED!r}; findings: {findings!r}"]
    return []
