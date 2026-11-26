# scenario: _dispatches_section keeps only the header when there are no entries
# inherits: hd=python/honest-render/honest-render.hd::_dispatches_section -> feature=specs/features/honest-render.feature::_dispatches_section keeps only the header when there are no entries
from honest_design import read_hd, render
from honest_render.render import _dispatches_section

_SOURCE = """module dispatch-fixture
  layer foundation
  dispatch unused = {}
"""


def probe_dispatches_section_no_entries():
    """Check the declared Dispatch section rows."""
    module = read_hd(_SOURCE)["ok"]["modules"][0]
    section = _dispatches_section(module, render(module))
    expected = {
        "heading": "Dispatches",
        "kind": "dispatches",
        "lines": [],
        "rows": [
            ["Dispatch", "Key", "Target"],
        ],
    }
    if section != expected:
        return [f"dispatch section was {section!r}, expected {expected!r}"]
    return []
