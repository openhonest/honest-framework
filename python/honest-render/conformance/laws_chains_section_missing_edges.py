# scenario: _chains_section shows a standalone link and does not infer missing edges
# inherits: hd=python/honest-render/honest-render.hd::_chains_section -> feature=specs/features/honest-render.feature::_chains_section shows a standalone link and does not infer missing edges
import re
from honest_design import read_hd, render
from honest_render.render import _chains_section

_SOURCE = """module chain-fixture
  layer foundation
  fn first : () -> int note "first link"
  fn second : () -> int note "second link"
  chain single = first
  chain many = first -> second
"""


def probe_chains_section_missing_edges():
    """Keep a single standalone link and never infer absent edges."""
    module = read_hd(_SOURCE)["ok"]["modules"][0]
    module["chains"] = [*module["chains"], {"name": "empty", "links": [], "note": ""}]
    diagram = render(module)
    diagram["edges"] = []
    section = _chains_section(module, diagram)
    actual = [re.findall(r"[A-Za-z_]+", line) for line in section["lines"]]
    expected = [["single", "first"], ["many"], ["empty"]]
    if section["kind"] != "chains" or section["rows"] or actual != expected:
        return [f"expected chain lines {expected!r} and no rows, got {section!r}"]
    return []
