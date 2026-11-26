# scenario: draw_diagram
"""honest-render conformance fragment for the `draw_diagram` scenario.

draw_diagram is honest-render's import seam to honest-design's static renderer (its side of
`import honest_design` for the Diagram). It hands the Module to honest-design's `render` and
returns, as data, the four-column Diagram honest-design drew -- the column-placed nodes and the
chain edges. honest-design's render is total and reports no fault, so this pull carries none, and
honest-render never recomputes column placement or edges; this pull is the only way it obtains the
layout.

The expected values are not invented. The scenario names "the four-column Diagram honest-design
drew, the column-placed nodes and the chain edges", so every expected value is computed by calling
the real honest-design `render` directly -- a DIFFERENT module's function, not the function under
test -- which makes this a pass-through check and not a circular oracle. The Module fed in is the
real one honest-design's own read_hd produced from a real .hd source, exactly as the orchestrator
would hand it over (read_ir -> draw_diagram).

At least one case pins a literal, non-trivial value a stub cannot satisfy: the Diagram's module
name is the literal "m" from the source, and the four columns carry the fixed indices 1..4 with the
fixed titles honest-design assigns. A stub `return {}` or `return []` produces neither, so this
probe is not vacuous.
"""

from honest_design import read_hd, render

from honest_render import draw_diagram


# A valid .hd module source honest-design's read_hd reads cleanly, matching the sibling read_ir
# fragment's fixture so the Module fed to draw_diagram is a real honest-design Module.
_VALID_SOURCE = (
    "module m\n"
    "  layer foundation\n"
    '  fn classify : (t: str) -> T | Fault note "test"\n'
)


def _design_module(source):
    """The bare Module honest-design read -- the exact value read_ir hands to draw_diagram."""
    return read_hd(source)["ok"]["modules"][0]


def _design_diagram(source):
    """The Diagram honest-design's own render drew from that Module: the pass-through oracle,
    a different module's function than draw_diagram, so this is not a circular oracle."""
    return render(_design_module(source))


# The fixed four column titles honest-design assigns, left to right (section 7). Literal, so a stub
# that recomputes nothing or returns {} fails.
_EXPECTED_TITLES = ["Input boundary", "Orchestrators", "Pure functions", "Output boundary"]
_EXPECTED_INDICES = [1, 2, 3, 4]


def probe_draw_diagram():
    """draw_diagram hands the Module to honest-design's render and returns, unchanged, the
    four-column Diagram honest-design drew -- the module name, the four column-placed node columns
    and the chain edges -- recomputing no column rule and no edge, and carrying no fault."""
    bad = []

    module = _design_module(_VALID_SOURCE)
    got = draw_diagram(module)

    # 1. The seam returns exactly what honest-design's render drew: no recomputation, no re-wrap.
    expected = _design_diagram(_VALID_SOURCE)
    if got != expected:
        bad.append(f"draw_diagram(module) -> {got!r}, expected honest-design's Diagram {expected!r} unchanged")

    # 2. Literal: the Diagram's module name is "m", taken straight from the source's module name.
    if not isinstance(got, dict) or got.get("module") != "m":
        bad.append(f"draw_diagram(module) module={got.get('module') if isinstance(got, dict) else got!r}, expected the literal 'm'")

    # 3. Literal: four columns, with the fixed indices 1..4 and the fixed titles, left to right.
    columns = got.get("columns") if isinstance(got, dict) else None
    if not isinstance(columns, list) or len(columns) != 4:
        bad.append(f"draw_diagram(module) columns={columns!r}, expected the four columns honest-design draws")
    else:
        indices = [c.get("index") for c in columns]
        titles = [c.get("title") for c in columns]
        if indices != _EXPECTED_INDICES:
            bad.append(f"draw_diagram(module) column indices={indices!r}, expected {_EXPECTED_INDICES!r}")
        if titles != _EXPECTED_TITLES:
            bad.append(f"draw_diagram(module) column titles={titles!r}, expected {_EXPECTED_TITLES!r}")

    # 4. The pull carries no fault: a plain Diagram dict, never an ok/err envelope or a Fault arm.
    if isinstance(got, dict) and ("ok" in got or "err" in got or got.get("is_err")):
        bad.append(f"draw_diagram(module) -> {got!r}, expected a bare Diagram carrying no fault")

    return bad


def run():
    bad = probe_draw_diagram()
    for line in bad:
        print(f"FAIL draw_diagram: {line}")
    print(f"draw_diagram probe: {0 if bad else 1} passed, {1 if bad else 0} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(run())
