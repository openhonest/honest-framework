# scenario: _routes_section keeps headerless route rows in declaration order
# inherits: hd=python/honest-render/honest-render.hd::_routes_section -> feature=specs/features/honest-render.feature::_routes_section keeps headerless route rows in declaration order
from honest_design import read_hd, render
from honest_render.render import _routes_section

_SOURCE = """module routes-fixture
  layer foundation
  boundary_in fn list_items : () -> int note "list the items"
  boundary_in fn create_item : () -> int note "create an item"
  route "GET /items" -> list_items
  route "POST /items" -> create_item
"""


def probe_routes_section_headerless_rows():
    """Keep the declared route rows in order, without a header."""
    module = read_hd(_SOURCE)["ok"]["modules"][0]
    section = _routes_section(module, render(module))
    expected = [["GET", "/items", "list_items"], ["POST", "/items", "create_item"]]
    if section["kind"] != "routes" or section["lines"] or section["rows"] != expected:
        return [f"expected only headerless route rows {expected!r}, got {section!r}"]
    return []
