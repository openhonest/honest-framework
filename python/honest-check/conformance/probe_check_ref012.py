"""Honest probe for honest-check's check_ref012 (feature Scenario: check_ref012).

check_ref012 runs HC-REF012 over one module's packaging dependencies. It invokes
declared_seams to collect the modules the declaration already names a cross-module
seam onto, then for each dependency in manifest_deps it skips one outside
workspace_module_names (an external package) and emits one HC-REF012 error for a
workspace dependency the declaration names no seam onto.

The declaration here names one seam onto honest-parse (reads
"honest-parse.parse_source"). Three cases pin the behaviour:
  - manifest depends only on honest-parse, already a declared seam -> [].
  - manifest also depends on honest-type, onto which the declaration names no
    seam -> one HC-REF012 error.
  - manifest depends on tree-sitter, not a workspace module -> [] (external).
A stub `return []` passes the two absence cases and fails the firing case, so the
one-error result is a non-trivial literal no empty body produces.

Inputs are a real Declaration parsed by honest-design's read_hd, the foreign shape
honest-check reads but never constructs.
"""

# A module whose one function names one cross-module seam: reads honest-parse.parse_source.
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
        "workspace": ["honest-parse", "honest-type"],
        "expect": [],
    },
    # honest-type is a workspace dependency the declaration names no seam onto: HC-REF012.
    {
        "manifest_deps": ["honest-parse", "honest-type"],
        "workspace": ["honest-parse", "honest-type"],
        "expect": [("HC-REF012", "error")],
    },
    # Absence: tree-sitter is an external package, no door to hold it to, skipped.
    {
        "manifest_deps": ["tree-sitter"],
        "workspace": ["honest-parse", "honest-type"],
        "expect": [],
    },
]


def probe_check_ref012():
    """check_ref012 emits one HC-REF012 error per workspace dependency with no declared seam."""
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
        if pairs != case["expect"]:
            bad.append(
                f"check_ref012(manifest_deps={case['manifest_deps']!r}, "
                f"workspace={case['workspace']!r}) -> {pairs!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
