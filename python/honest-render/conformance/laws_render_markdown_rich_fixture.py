# scenario: render_markdown matches the stored rich Markdown fixture byte for byte
# inherits: hd=python/honest-render/honest-render.hd::render_markdown -> feature=specs/features/honest-render.feature::render_markdown matches the stored rich Markdown fixture byte for byte
"""A hand-authored Markdown fixture for a fixed ViewModel.

The fixture fixes blank lines, table padding and list-cell spacing where the
specification leaves exact punctuation open.
"""

from copy import deepcopy
from difflib import unified_diff
from pathlib import Path

from honest_render import render_markdown

_FIXTURE = Path(__file__).with_name("fixtures") / "rich_render.md"
_VIEW = {
    "module_name": "catalog",
    "sections": [
        {"heading": "Catalog", "kind": "heading",
         "lines": ["The catalog lists available items.", "A second paragraph explains the order."], "rows": []},
        {"heading": "Types", "kind": "types", "lines": [],
         "rows": [["Type", "Field", "Type"], ["Item", "title", "str"]]},
        {"heading": "Sets", "kind": "sets", "lines": [], "rows": [["Set", "Member"], ["modes", "plain"]]},
        {"heading": "Vocabularies", "kind": "vocabularies", "lines": [],
         "rows": [["Vocabulary", "Sets"], ["Mode", "modes"]]},
        {"heading": "Dispatches", "kind": "dispatches", "lines": [],
         "rows": [["Dispatch", "Key", "Target"], ["by_mode", "plain", "prepare"]]},
        {"heading": "Chains", "kind": "chains", "lines": ["main: receive -> coordinate", "preview: prepare"], "rows": []},
        {"heading": "Routes", "kind": "routes", "lines": [],
         "rows": [["GET", "/catalog", "receive"], ["POST", "/catalog", "receive"]]},
        {"heading": "Entries", "kind": "entries", "lines": [],
         "rows": [["import catalog", "receive"], ["call:preview", "receive"]]},
    ],
}


def probe_render_markdown_rich_fixture():
    expected = _FIXTURE.read_bytes()
    view = deepcopy(_VIEW)
    first = render_markdown(view).encode("utf-8")
    second = render_markdown(view).encode("utf-8")
    failures = []
    if first != expected:
        diff = "".join(unified_diff(
            expected.decode("utf-8").splitlines(keepends=True),
            first.decode("utf-8").splitlines(keepends=True),
            fromfile="stored Markdown",
            tofile="rendered Markdown",
        ))
        failures.append(f"Markdown differs from the stored fixture:\n{diff}")
    if second != first:
        failures.append("Repeated rendering produced different bytes")
    if view != _VIEW:
        failures.append("Rendering mutated the ViewModel")
    return failures
