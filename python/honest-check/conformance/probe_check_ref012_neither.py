# scenario: check_ref012
# inherits: hd=python/honest-check/honest-check.hd::check_ref012 -> feature=specs/features/honest-check.feature::check_ref012 errors on a dependency with neither a seam nor a pure call -> test=python/honest-check/conformance/probe_check_ref012_neither.py::probe_check_ref012_neither
"""Honest probe for check_ref012's "neither a seam nor a pure call" scenario.

The scenario: a module whose manifest depends on a workspace module `utils`, but
whose declaration names neither a declared side-effect seam onto utils nor any
resolved cross-module pure_call onto utils, must produce one HC-REF012 error for
the utils dependency at error severity. The orchestrator has already subtracted
from manifest_deps every dependency a resolved pure dependency evidences, so a
dependency reaching check_ref012 (utils, still in manifest_deps) is covered by
neither kind of coupling, and check_ref012 fires on it.

The module under test (_SRC_MODULE) declares one function with one seam onto
honest-parse and no coupling of any kind onto utils. Three cases pin the firing:
  - manifest depends only on honest-parse, a declared seam -> [] (no fault).
  - manifest also carries utils, a workspace module with neither a seam nor a
    pure_call onto it -> exactly one HC-REF012 error naming utils, at error
    severity. This is the scenario's firing case.
  - manifest depends on tree-sitter, outside workspace_module_names -> [] (an
    external package, no door to hold it to, skipped).

A stub `return []` passes both absence cases and fails the firing case, so the
one-error result (with "utils" named in its text) is a non-trivial literal no
empty body produces. Inputs are a real Declaration parsed by honest-design's
read_hd, the foreign IR honest-check reads but never constructs.
"""

# A module whose one function names one cross-module seam onto honest-parse and
# names NO coupling (neither seam nor pure_call) onto utils.
_SRC_MODULE = (
    "module demo\n\n"
    '  fn caller : (x: str) -> str side_effect reads "honest-parse.parse_source"\n'
)

# Each case: the manifest dependency list, the workspace module names, and the
# ordered (rule_id, severity) pairs check_ref012 must return.
_CASES = [
    # The one dependency is already a declared seam: nothing to force onto the record.
    {
        "manifest_deps": ["honest-parse"],
        "workspace": ["honest-parse", "utils"],
        "expect": [("HC-REF012", "error")],
        "fire": False,
    },
    # utils is a workspace dependency this declaration covers with neither a seam
    # nor a pure_call: one HC-REF012 error at error severity naming utils.
    {
        "manifest_deps": ["honest-parse", "utils"],
        "workspace": ["honest-parse", "utils"],
        "expect": [("HC-REF012", "error")],
        "fire": True,
    },
    # Absence: tree-sitter is an external package, no door to hold it to, skipped.
    {
        "manifest_deps": ["tree-sitter"],
        "workspace": ["honest-parse", "utils"],
        "expect": [("HC-REF012", "error")],
        "fire": False,
    },
]


def probe_check_ref012_neither():
    """check_ref012 emits one HC-REF012 error naming utils, a workspace dependency with neither a seam nor a pure call onto it."""
    try:
        from honest_check import check_ref012
    except ImportError as exc:
        return [f"cannot import check_ref012: {exc}"]
    try:
        from honest_design import read_hd
    except ImportError as exc:
        return [f"cannot import honest_design.read_hd: {exc}"]

    module = read_hd(_SRC_MODULE)["ok"]["modules"][0]

    bad = []
    for case in _CASES:
        got = check_ref012(
            module=module,
            manifest_deps=case["manifest_deps"],
            workspace_module_names=case["workspace"],
            path="demo/demo.hd",
        )
        pairs = [(d["rule_id"], d["severity"]) for d in got]
        expected = case["expect"] if case["fire"] else []
        if pairs != expected:
            bad.append(
                f"check_ref012(manifest_deps={case['manifest_deps']!r}, "
                f"workspace={case['workspace']!r}) -> {pairs!r}, "
                f"expected {expected!r}"
            )
        # The firing case must name the utils dependency in the diagnostic.
        if case["fire"]:
            names_utils = any("utils" in str(d) for d in got)
            if not names_utils:
                bad.append(
                    f"check_ref012(manifest_deps={case['manifest_deps']!r}) "
                    f"HC-REF012 diagnostic does not name 'utils': {got!r}"
                )
    return bad
