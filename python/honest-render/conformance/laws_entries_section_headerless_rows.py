# scenario: _entries_section keeps headerless entry rows in declaration order
# inherits: hd=python/honest-render/honest-render.hd::_entries_section -> feature=specs/features/honest-render.feature::_entries_section keeps headerless entry rows in declaration order
from honest_design import read_hd, render
from honest_render.render import _entries_section

_SOURCE = """module entries-fixture
  layer foundation
  boundary_in fn open_items : () -> int note "open the items"
  boundary_in fn close_items : () -> int note "close the items"
  entry "cli:open" -> open_items
  entry "export:close" -> close_items
"""


def probe_entries_section_headerless_rows():
    """Keep the declared entry rows in order, without a header."""
    module = read_hd(_SOURCE)["ok"]["modules"][0]
    section = _entries_section(module, render(module))
    expected = [["cli:open", "open_items"], ["export:close", "close_items"]]
    if section["kind"] != "entries" or section["lines"] or section["rows"] != expected:
        return [f"expected only headerless entry rows {expected!r}, got {section!r}"]
    return []
