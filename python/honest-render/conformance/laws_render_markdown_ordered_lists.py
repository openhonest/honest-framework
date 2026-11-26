# scenario: render_markdown renders routes and entries as ordered lists
# inherits: hd=python/honest-render/honest-render.hd::render_markdown -> feature=specs/features/honest-render.feature::render_markdown renders routes and entries as ordered lists
import re

from honest_render import render_markdown

_VIEW = {
    "module_name": "list-fixture",
    "sections": [
        {
            "heading": "Routes",
            "kind": "routes",
            "lines": [],
            "rows": [["POST", "/zulu", "create_zulu"], ["GET", "/alpha", "read_alpha"]],
        },
        {
            "heading": "Entries",
            "kind": "entries",
            "lines": [],
            "rows": [["CLI dispatch", "serve_zulu"], ["Package import", "serve_alpha"]],
        },
    ],
}
_EXPECTED = (
    ("Routes", (("POST", "/zulu", "create_zulu"), ("GET", "/alpha", "read_alpha"))),
    ("Entries", (("CLI dispatch", "serve_zulu"), ("Package import", "serve_alpha"))),
)


def probe_render_markdown_ordered_lists():
    """Keep each ordered route and entry row, preserving its fields."""
    output = render_markdown(_VIEW)
    sections = {}
    heading = None
    for line in output.splitlines():
        match = re.fullmatch(r"#{1,6}[ \t]+(.+?)[ \t]*", line)
        if match:
            heading = match[1]
            sections[heading] = []
        elif heading is not None and line.strip():
            sections[heading].append(line)

    failures = []
    for heading, expected in _EXPECTED:
        lines = sections.get(heading, [])
        items = [re.fullmatch(r"\s*\d+[.)][ \t]+(.*)", line) for line in lines]
        if len(items) != len(expected) or not all(items):
            failures.append(f"{heading} should contain exactly two Markdown ordered items, got {lines!r}")
            continue
        for match, fields in zip(items, expected):
            if not all(field in match[1] for field in fields):
                failures.append(f"{heading} item {match[1]!r} did not carry expected fields {fields!r}")
    return failures
