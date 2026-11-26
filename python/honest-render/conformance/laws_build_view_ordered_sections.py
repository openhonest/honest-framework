# scenario: build_view preserves declared facts in ordered view sections
# inherits: hd=python/honest-render/honest-render.hd::build_view -> feature=specs/features/honest-render.feature::build_view preserves declared facts in ordered view sections
"""Project authored declarations into a complete, ordered ViewModel."""

from honest_design import read_hd, render
from honest_render import build_view

_DECLARATION = """module catalog
  layer foundation
  version "v2"
  note "The catalog lists available items."
  inputs = { "file:catalog" : "item data" }
  outputs = { "file:document" : "catalog document" }

  type Item = { title: str count: int }
  set modes = { "plain", "checked" }
  set extra_modes = { "preview" }
  vocabulary Mode = { modes, extra_modes }
  dispatch by_mode = { "plain" -> prepare, "checked" -> prepare }

  boundary_in fn receive : (mode: Mode) -> Item invokes coordinate awaited
    side_effect reads "file:catalog" note "Accepts the chosen catalog mode."
  orchestrator fn coordinate : (mode: Mode) -> Item invokes prepare, deliver awaited
    note "Prepares and writes the result."
  fn prepare : (mode: Mode, labels: dict<str, int>) -> Item | NOTHING
  boundary_out fn deliver : (item: Item) -> Item awaited side_effect writes "file:document"
    note "Writes the catalog document."

  chain main = receive -> coordinate -> deliver
  chain preview = receive -> coordinate
  route "GET /catalog" -> receive
  route "POST /catalog" -> receive
  entry "import catalog" -> receive
  entry "call:preview" -> receive
  expose component item_card note "A catalog entry."
  surfaces catalog_page = [ "top" as header, "details" as article ]
  example first_item of main = "Show the first item."
"""
_KINDS = (
    "heading", "world", "functions", "types", "sets", "vocabularies", "dispatches",
    "chains", "routes", "entries", "exposes", "surfaces", "examples",
)
_LABELS = (
    "catalog", "World", "Functions", "Types", "Sets", "Vocabularies", "Dispatches",
    "Chains", "Routes", "Entries", "Exposes", "Surfaces", "Examples",
)
_ROWS = {
    "types": [["Type", "Field", "Type"], ["Item", "title", "str"], ["Item", "count", "int"]],
    "sets": [["Set", "Member"], ["modes", "plain"], ["modes", "checked"], ["extra_modes", "preview"]],
    "vocabularies": [["Vocabulary", "Sets"], ["Mode", "modes, extra_modes"]],
    "dispatches": [["Dispatch", "Key", "Target"], ["by_mode", "plain", "prepare"],
                   ["by_mode", "checked", "prepare"]],
    "routes": [["GET", "/catalog", "receive"], ["POST", "/catalog", "receive"]],
    "entries": [["import catalog", "receive"], ["call:preview", "receive"]],
}
_LINES = {
    "heading": ["name: catalog", "layer: foundation", "version: v2", "The catalog lists available items."],
    "world": ["reads file:catalog: item data", "writes file:document: catalog document"],
    "functions": [
        "[Input boundary] receive", "boundary_in: receive(mode: Mode) -> Item",
        "invokes: coordinate", "reads file:catalog", "awaited", "Accepts the chosen catalog mode.",
        "[Orchestrators] coordinate", "orchestrator: coordinate(mode: Mode) -> Item",
        "invokes: prepare, deliver", "awaited", "Prepares and writes the result.",
        "[Pure functions] prepare", "fn: prepare(mode: Mode, labels: dict[str, int]) -> Item | NOTHING", "(none)",
        "[Output boundary] deliver", "boundary_out: deliver(item: Item) -> Item",
        "writes file:document", "awaited", "Writes the catalog document.",
    ],
    "chains": ["main: receive -> coordinate, coordinate -> deliver", "preview: receive -> coordinate"],
}
_OPTIONAL_FACTS = {
    "exposes": ("component", "item_card", "A catalog entry."),
    "surfaces": ("catalog_page", "top", "header", "details", "article"),
    "examples": ("first_item", "main", "Show the first item."),
}


def probe_build_view_ordered_sections():
    module = read_hd(_DECLARATION)["ok"]["modules"][0]
    view = build_view(module, render(module))
    sections = view.get("sections", ())
    failures = []
    if view.get("module_name") != "catalog":
        failures.append(f"Expected module_name catalog, got {view.get('module_name')!r}")
    fields = ("heading", "kind", "lines", "rows")
    if any(set(section) != set(fields) for section in sections):
        failures.append("Every ViewSection must carry heading, kind, lines, and rows")
        return failures
    labels = tuple((section["kind"], section["heading"]) for section in sections)
    expected = tuple(zip(_KINDS, _LABELS))
    if labels != expected:
        failures.append(f"Expected ordered sections {expected!r}, got {labels!r}")
        return failures
    for section in sections:
        kind = section["kind"]
        expected_rows = _ROWS.get(kind, [])
        if section["rows"] != expected_rows:
            failures.append(f"{kind}: expected rows {expected_rows!r}, got {section['rows']!r}")
        if kind in _OPTIONAL_FACTS:
            text = " ".join(section["lines"])
            positions = [text.find(fact) for fact in _OPTIONAL_FACTS[kind]]
            if -1 in positions or positions != sorted(positions):
                failures.append(f"{kind}: declared facts missing or reordered in {text!r}")
        else:
            expected_lines = _LINES.get(kind, [])
            if section["lines"] != expected_lines:
                failures.append(f"{kind}: expected lines {expected_lines!r}, got {section['lines']!r}")
    return failures
