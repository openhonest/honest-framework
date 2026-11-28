# scenario: check_ref012
# inherits: hd=python/honest-check/honest-check.hd::check_ref012 -> feature=specs/features/honest-check.feature::check_ref012 accepts a resolved pure call as dependency evidence -> test=python/honest-check/conformance/probe_check_ref012_pure_call_satisfies.py::probe_check_ref012_pure_call_satisfies
"""A resolved pure call satisfies a manifest dependency the same way a seam does.

The scenario (feature Scenario: check_ref012 accepts a resolved pure call as
dependency evidence) fixes one claim: a caller whose package manifest depends on a
workspace module `utils`, that declares NO side-effect seam onto utils, but DOES
carry a resolved `pure_call "utils.answer"` onto a function utils publishes as a
pure way in, produces NO HC-REF012 error for the utils dependency. The resolved
pure dependency satisfies the manifest dependency, exactly as a side-effect seam
would.

The scenario states the orchestrator does the subtraction: run_seam_rules removes
the dependencies a resolved pure call evidences from the caller's manifest_deps
before check_ref012 runs. So the satisfaction path is exercised by driving the
orchestrator run_seam_rules, exactly as probe_run_seam_rules_scoped_pure_calls.py
does, not by calling check_ref012 directly with a hand-subtracted list.

For the pure call to be RESOLVED (and thus subtracted), utils must publish
`answer` as a pure way in: a plain `fn` with no side effects, exposed through a
valid `entry` (or export). utils here declares `fn answer` with no side effect and
publishes it with `entry "import utils" -> answer`.

The caller declares a single plain `fn use` carrying only `pure_call "utils.answer"`
and NO side effect onto utils, so the only coupling to utils is the pure call. The
manifest names utils as a dependency of caller. The claim: run_seam_rules reports
NO HC-REF012 naming utils.

A stub run_seam_rules returning [] would pass this single-claim probe vacuously,
so a non-trivial FIRING row pins the firing side: a second caller `bare` that
depends on `utils` in its manifest with NO seam and NO pure call onto utils MUST
draw exactly one HC-REF012 naming utils. The two rows together — one that must be
silent for the resolved pure call, one that must fire for the bare dependency —
cannot both be satisfied by any empty-body stub (a stub that returns [] fails the
firing row; a stub that always emits HC-REF012 fails the resolved row).
"""

# caller couples to utils ONLY through a resolved pure_call onto utils.answer;
# it declares no side-effect seam onto utils. Its manifest depends on utils.
_CALLER = (
    "module caller\n"
    '  fn use : () -> int pure_call "utils.answer" note "uses the pure answer"\n'
)
# bare depends on utils in its manifest but couples to it with neither a seam
# nor a pure call: HC-REF012 must fire for utils here.
_BARE = (
    "module bare\n"
    '  fn run : () -> int note "touches utils only through the manifest"\n'
)
# utils publishes answer as a pure way in: plain fn, no side effect, exported via entry.
_UTILS = (
    "module utils\n"
    '  fn answer : () -> int note "returns one"\n'
    '  entry "import utils" -> answer\n'
)

_PATHS = {
    "caller": "packages/caller/caller.hd",
    "bare": "packages/bare/bare.hd",
    "utils": "packages/utils/utils.hd",
}
_MANIFEST_DEPS = {"caller": ["utils"], "bare": ["utils"]}


def _ref012_for_utils(findings):
    return [
        f
        for f in findings
        if f["rule_id"] == "HC-REF012" and "utils" in f["message"]
    ]


def probe_check_ref012_pure_call_satisfies():
    """A resolved pure call onto a published pure fn satisfies the manifest dependency, like a seam."""
    try:
        from honest_check.seams import run_seam_rules
    except ImportError as exc:
        return [f"cannot import run_seam_rules: {exc}"]
    try:
        from honest_design import read_hd
    except ImportError as exc:
        return [f"cannot import honest_design.read_hd: {exc}"]

    modules = [
        read_hd(source)["ok"]["modules"][0]
        for source in (_CALLER, _BARE, _UTILS)
    ]
    declarations = {module["name"]: module for module in modules}

    bad = []

    # The resolved-pure-call caller: NO HC-REF012 for utils.
    resolved = run_seam_rules(
        declarations=declarations,
        paths=_PATHS,
        manifest_deps=_MANIFEST_DEPS,
        in_scope=["caller"],
    )
    resolved_utils = _ref012_for_utils(resolved)
    if resolved_utils:
        bad.append(
            "resolved pure call: run_seam_rules emitted HC-REF012 for utils "
            f"when caller's pure_call \"utils.answer\" should satisfy it; got {resolved!r}"
        )

    # The bare dependency caller: exactly one HC-REF012 for utils.
    bare = run_seam_rules(
        declarations=declarations,
        paths=_PATHS,
        manifest_deps=_MANIFEST_DEPS,
        in_scope=["bare"],
    )
    bare_utils = _ref012_for_utils(bare)
    if len(bare_utils) != 1:
        bad.append(
            "bare dependency: run_seam_rules must emit exactly one HC-REF012 for "
            f"utils (no seam, no pure call), got {len(bare_utils)}; findings {bare!r}"
        )

    return bad


if __name__ == "__main__":
    failures = probe_check_ref012_pure_call_satisfies()
    if failures:
        for line in failures:
            print("FAIL:", line)
        raise SystemExit(1)
    print("probe_check_ref012_pure_call_satisfies: PASS")
