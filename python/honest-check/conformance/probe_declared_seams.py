"""Honest probe for honest-check's declared_seams (feature Scenario: declared_seams).

declared_seams reads one parsed .hd module and collects its cross-module seams.
For each function and each side effect it declares, a side effect whose module
half is the empty string names the world (writes "DOM", reads "env:POOL_SIZE")
and is skipped; a side effect whose module half is non-empty becomes one Seam
carrying the function name as caller, the named module, the door (the dotted
target's door half, the empty string when the target named only a module), and
the direction. The seams-bearing case pins two concrete Seam records; the
world-only case is the explicit absence (no module named, so no seam). A stub
`return []` passes only the world-only case and fails the seams case.

The module inputs are real Declarations: honest-design's read_hd parses the .hd
text into the foreign shape honest-check reads but never constructs.
"""

# A module whose one function declares three side effects: a dotted cross-module
# reach (honest-parse.parse_source), a world write (DOM, skipped), and a bare
# cross-module reach (honest-persist, kept with an empty door).
_SRC_SEAMS = (
    "module demo\n\n"
    '  fn caller : (x: str) -> str'
    ' side_effect reads "honest-parse.parse_source"'
    ' side_effect writes "DOM"'
    ' side_effect reads "honest-persist"\n'
)

# A module whose only side effects name the world: nothing to resolve, no seams.
_SRC_WORLD_ONLY = (
    "module demo\n\n"
    '  fn caller : (x: str) -> str'
    ' side_effect writes "DOM"'
    ' side_effect reads "env:POOL_SIZE"\n'
)

# Each case: the .hd text to parse into a Declaration, and the exact seam list
# declared_seams must return off it.
_CASES = [
    {
        "src": _SRC_SEAMS,
        "expect": [
            {"caller": "caller", "module": "honest-parse", "door": "parse_source", "direction": "reads"},
            {"caller": "caller", "module": "honest-persist", "door": "", "direction": "reads"},
        ],
    },
    # Absence: a module declaring only world-named side effects yields no seams.
    {"src": _SRC_WORLD_ONLY, "expect": []},
]


def probe_declared_seams():
    """declared_seams collects one module's cross-module side effects into Seams."""
    try:
        from honest_check import declared_seams
    except ImportError as exc:
        return [f"cannot import declared_seams: {exc}"]
    try:
        from honest_design import read_hd
    except ImportError as exc:
        return [f"cannot import honest_design.read_hd: {exc}"]

    bad = []
    for case in _CASES:
        module = read_hd(case["src"])["ok"]["modules"][0]
        got = declared_seams(module=module)
        if got != case["expect"]:
            bad.append(
                f"declared_seams({case['src']!r}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
