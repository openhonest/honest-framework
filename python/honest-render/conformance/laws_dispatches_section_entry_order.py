# scenario: _dispatches_section preserves dispatch and entry order
# inherits: hd=python/honest-render/honest-render.hd::_dispatches_section -> feature=specs/features/honest-render.feature::_dispatches_section preserves dispatch and entry order
from honest_design import read_hd, render
from honest_render.render import _dispatches_section

_SOURCE = """module dispatch-fixture
  layer foundation
  fn send : () -> int note "a handler"
  fn start : () -> int note "another handler"
  fn move : () -> int note "a handler for the second listed dispatch"
  dispatch second = { "z" -> send from slice, "a" -> start }
  dispatch first = { "m" -> move }
"""


def probe_dispatches_section_entry_order():
    """Check the declared Dispatch section rows."""
    module = read_hd(_SOURCE)["ok"]["modules"][0]
    section = _dispatches_section(module, render(module))
    expected = {
        "heading": "Dispatches",
        "kind": "dispatches",
        "lines": [],
        "rows": [
            ["Dispatch", "Key", "Target"],
            ["second", "z", "send"],
            ["second", "a", "start"],
            ["first", "m", "move"],
        ],
    }
    if section != expected:
        return [f"dispatch section was {section!r}, expected {expected!r}"]
    return []
