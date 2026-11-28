# scenario: check_ref012
# inherits: hd=python/honest-check/honest-check.hd::check_ref012 -> feature=specs/features/honest-check.feature::check_ref012 errors on a dependency whose only pure call is non-callable -> test=python/honest-check/conformance/probe_check_ref012_noncallable.py::probe_check_ref012_noncallable
"""A dependency whose only pure call names a non-callable target gets no evidence and still errors.

The orchestrator run_seam_rules subtracts, before calling check_ref012, every
manifest dependency a RESOLVED pure call evidences. A pure call whose target is
not a callable pure way in (here utils.helper is a plain fn utils publishes
through no entry and no export, an interior function) resolves as invalid_role,
not resolved, so it evidences nothing: the dependency onto utils survives the
subtraction and reaches check_ref012, which — finding no I/O seam onto utils
either — emits one HC-REF012 error for utils.

Fixtures are built as probe_run_seam_rules_scoped_pure_calls.py builds them:
real Declarations parsed by honest-design's read_hd, run through run_seam_rules
with the whole declarations map, the caller's manifest_deps naming utils, and
only the caller in scope. utils is present in declarations and outside the
reporting scope.

The caller's only annotation onto utils is the non-callable pure_call, which
resolve_pure_calls marks invalid_role; pure_call_findings reports that as one
HC-REF007 at the caller path. So the expected result is exactly two findings,
both at the caller path: HC-REF007 for the invalid pure target and HC-REF012
for the dependency utils that nothing covered.

A stub run_seam_rules that returns [] fails this probe: the expected list is a
non-empty literal, so an empty body cannot produce it.
"""

# The caller depends on workspace module `utils` and names it only through one
# pure_call onto a non-callable target. No side-effect seam onto utils exists.
# utils publishes `answer` through an entry but leaves `helper` interior, so a
# pure_call onto utils.helper is not a callable pure way in: invalid_role.
_DECLARATIONS = [
    'module caller\n  fn use : () -> int pure_call "utils.helper" note "calls an interior function"\n',
    'module utils\n'
    '  fn answer : () -> int note "the published pure way in"\n'
    '  fn helper : () -> int note "an interior function no entry reaches"\n'
    '  entry "import utils" -> answer\n',
]
_PATHS = {
    "caller": "packages/caller/caller.hd",
    "utils": "packages/utils/utils.hd",
}
# Both findings land at the caller's .hd path. The pure call fails the callable
# check (invalid_role -> HC-REF007), and utils, unevidenced by any coupling,
# earns its HC-REF012.
_EXPECTED = [
    ("HC-REF007", "error", _PATHS["caller"]),
    ("HC-REF012", "error", _PATHS["caller"]),
]
# HC-REF012's message must name the uncovered dependency module.
_NAMES = {"HC-REF012": ("utils",)}


def probe_check_ref012_noncallable():
    """A dependency whose only pure call is non-callable still earns its HC-REF012 error."""
    try:
        from honest_check.seams import run_seam_rules
    except ImportError as exc:
        return [f"cannot import run_seam_rules: {exc}"]
    from honest_design import read_hd

    modules = [read_hd(source)["ok"]["modules"][0] for source in _DECLARATIONS]
    findings = run_seam_rules(
        declarations={module["name"]: module for module in modules},
        paths=_PATHS,
        manifest_deps={"caller": ["utils"]},
        in_scope=["caller"],
    )
    got = sorted(
        (finding["rule_id"], finding["severity"], finding["source_location"])
        for finding in findings
    )
    if got != _EXPECTED:
        return [
            f"run_seam_rules returned {got!r}, expected {_EXPECTED!r}; "
            f"findings: {findings!r}"
        ]
    by_rule = {finding["rule_id"]: finding for finding in findings}
    for rule_id in _NAMES:
        if rule_id not in by_rule:
            return [f"no finding for {rule_id!r} whose message names {_NAMES[rule_id]!r}"]
        finding = by_rule[rule_id]
        for name in _NAMES[rule_id]:
            if name not in finding["message"]:
                return [
                    f"{finding['rule_id']} message {finding['message']!r} "
                    f"does not name {name!r}"
                ]
    return []
