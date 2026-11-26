# scenario: _render_ordered_list numbers route and entry rows without table syntax
# inherits: hd=python/honest-render/honest-render.hd::_render_ordered_list -> feature=specs/features/honest-render.feature::_render_ordered_list numbers route and entry rows without table syntax
import re
from honest_render.render import _render_ordered_list

_CASES = [
    {"heading": "Routes", "kind": "routes", "lines": [],
     "rows": [["POST", "/zulu", "create_zulu"], ["GET", "/alpha", "read_alpha"]]},
    {"heading": "Entries", "kind": "entries", "lines": [],
     "rows": [["cli:open", "open_items"], ["export:close", "close_items"]]},
]


def probe_render_ordered_list_route_entry_rows():
    """Render one numbered item per input row, with cells in supplied order."""
    failures = []
    for section in _CASES:
        rendered = _render_ordered_list(section)
        nonempty = [line for line in rendered.splitlines() if line.strip()]
        heading = section["heading"]
        if len(nonempty) != 3 or not re.fullmatch(rf"#{{1,6}}\s+{heading}", nonempty[0]):
            failures.append(f"expected {heading} heading and two numbered items, got {rendered!r}")
            continue
        for line, fields in zip(nonempty[1:], section["rows"]):
            match = re.fullmatch(r"\s*\d+[.)]\s+(.*)", line)
            literal_order = r".*?".join(re.escape(field) for field in fields)
            if not match or not re.search(literal_order, match[1]):
                failures.append(f"expected one numbered {heading} item with {fields!r}, got {line!r}")
    return failures
