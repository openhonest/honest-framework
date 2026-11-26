# scenario: _render_ordered_list leaves only the heading for an empty section
# inherits: hd=python/honest-render/honest-render.hd::_render_ordered_list -> feature=specs/features/honest-render.feature::_render_ordered_list leaves only the heading for an empty section
import re
from honest_render.render import _render_ordered_list

_SECTION = {"heading": "Routes", "kind": "routes", "lines": [], "rows": []}


def probe_render_ordered_list_empty_section():
    """Keep the Markdown heading when the view supplies no list items."""
    rendered = _render_ordered_list(_SECTION)
    if not re.fullmatch(r"#{1,6}\s+Routes", rendered.strip()):
        return [f"expected only a Routes heading, got {rendered!r}"]
    return []
