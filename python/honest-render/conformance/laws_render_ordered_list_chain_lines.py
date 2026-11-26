# scenario: _render_ordered_list numbers chain lines in supplied order
# inherits: hd=python/honest-render/honest-render.hd::_render_ordered_list -> feature=specs/features/honest-render.feature::_render_ordered_list numbers chain lines in supplied order
import re
from honest_render.render import _render_ordered_list

_SECTION = {"heading": "Chains", "kind": "chains", "lines": ["first", "second"], "rows": []}


def probe_render_ordered_list_chain_lines():
    """Render each chain line as an ordered Markdown item."""
    rendered = _render_ordered_list(_SECTION)
    nonempty = [line for line in rendered.splitlines() if line.strip()]
    if len(nonempty) != 3 or not re.fullmatch(r"#{1,6}\s+Chains", nonempty[0]):
        return [f"expected Chains heading and two numbered items, got {rendered!r}"]
    items = [re.fullmatch(r"\s*\d+[.)]\s+(.*)", line) for line in nonempty[1:]]
    if not all(items) or [match[1] for match in items] != ["first", "second"]:
        return [f"expected numbered first and second items in that order, got {rendered!r}"]
    return []
