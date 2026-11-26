"""honest-render: the public static renderer of one .hd declaration.

Read the file, get honest-design's Module and Diagram, build a ViewModel, render Markdown, write it
out. Read-only and deterministic; it never parses .hd and never recomputes layout. I/O lives at the
boundaries (read_source, the two import seams read_ir/draw_diagram, write_document); the pure core
(build_view, render_markdown, render_fault) takes data and returns data. Faults travel in the return
value as a bare union arm (value | Fault), never raised.

Section builders and renderers are selected in declaration order through tables. Their pure
helpers build view sections and Markdown without reaching outside the given inputs.
"""

import contextlib
import sys

import honest_design
from honest_type import is_fault

from honest_render._util import _pick

_OMITTED = "(none)"


# --- the pure fault constructor -------------------------------------------------------------------

# The three honest-render-originated faults (section 3b), as a closed table keyed on code: each row
# carries the category and message words for that code. render_declaration builds file_unreadable and
# write_failed from this table through render_fault; read_ir builds not_single_module from the same
# table as bare data (its .hd invokes is empty, so it may not call render_fault). The table is the one
# place the code-to-category/message mapping lives, so the two originated boundary faults are not two
# shape-identical builders (HC-P014) but one construction over data.
_FAULT_WORDS = {
    "file_unreadable": {
        "category": "client",
        "message": "the .hd path could not be read; check the path exists and is readable",
    },
    "write_failed": {
        "category": "server",
        "message": "the destination could not be written; check the output path is writable",
    },
    "not_single_module": {
        "category": "client",
        "zero_message": "The .hd declares no modules. Supply exactly one module to render.",
        "multiple_message": "The .hd declares multiple modules. Render them one module at a time.",
    },
}


# hd: render_fault
def render_fault(code, category, message, detail):
    """Assemble one honest-render Fault record from its four parts. The reserved is_err tag is always
    true, and code/category/message/detail are carried through unchanged. Pure: it reads no world."""
    return {
        "is_err": True,
        "code": code,
        "category": category,
        "message": message,
        "detail": detail,
    }


# --- the reader on the filesystem side ------------------------------------------------------------


# hd: read_source
def read_source(hd_path):
    """Read the .hd file's text and report a plain ReadOutcome. Thin: it builds no Fault. ok true with
    the file text on a clean read; ok false with the read error in detail on a failure. It catches the
    OS error at this input boundary and reports it as data, never a raise."""
    try:
        with open(hd_path, encoding="utf-8") as handle:
            return {"ok": True, "text": handle.read(), "detail": ""}
    except OSError as exc:
        return {"ok": False, "text": "", "detail": str(exc)}


# --- the import seams to honest-design ------------------------------------------------------------

# honest-render renders exactly one module per .hd (section 3b). One honest-design read_hd result
# carries either an ok Document or an err Fault. The err arm read_ir surfaces is honest-design's own
# Fault, passed through unchanged. The ok arm carries a Document whose modules list read_ir resolves
# to exactly one Module: a one-module Document yields that Module; a zero- or multi-module Document
# yields honest-render's client not_single_module Fault as bare data, built from the _FAULT_WORDS row
# with the count in detail and a remedy for the observed count. read_ir's .hd invokes is empty, so it may not call render_fault; this
# builder assembles the same Fault shape as bare data. Closed two-row choices (P01), so no arm or
# count falls through (P16) and no `modules[0]` runs on an empty list.
_not_single_module_fault = lambda count: {
    "is_err": True,
    "code": "not_single_module",
    "category": _FAULT_WORDS["not_single_module"]["category"],
    "message": _pick(
        count == 0,
        lambda: _FAULT_WORDS["not_single_module"]["zero_message"],
        lambda: _FAULT_WORDS["not_single_module"]["multiple_message"],
    ),
    "detail": {"module_count": str(count)},
}
_resolve_ok_modules = lambda modules: _pick(
    len(modules) == 1,
    lambda: modules[0],
    lambda: _not_single_module_fault(len(modules)),
)
_read_ir_arm = lambda result: _pick(
    "err" in result,
    lambda: result["err"],
    lambda: _resolve_ok_modules(result["ok"]["modules"]),
)


# inherits: hd=python/honest-render/honest-render.hd::read_ir -> feature=specs/features/honest-render.feature::read_ir -> test=python/honest-render/conformance/laws_read_ir.py::probe_read_ir
# inherits: hd=python/honest-render/honest-render.hd::read_ir -> feature=specs/features/honest-render.feature::read_ir asks the caller to supply one module when none are declared -> test=python/honest-render/conformance/laws_read_ir_zero_module_remedy.py::probe_read_ir_zero_module_remedy
# inherits: hd=python/honest-render/honest-render.hd::read_ir -> feature=specs/features/honest-render.feature::read_ir asks the caller to render multiple declared modules individually -> test=python/honest-render/conformance/laws_read_ir_multiple_module_remedy.py::probe_read_ir_multiple_module_remedy
# hd: read_ir
def read_ir(source):
    """Hand the .hd source text to honest-design's read_hd and resolve its Document to exactly one
    Module (section 3b). On a one-module Document it returns that bare Module; on a zero- or
    multi-module Document it returns the client not_single_module Fault as data, its detail stating the
    module count; on a read_hd fault it passes that bare Fault through unchanged (recognized by
    is_fault). honest-render never parses .hd itself; this pull is the only way it obtains a Module."""
    return _read_ir_arm(honest_design.read_hd(source))


# hd: draw_diagram
def draw_diagram(module):
    """Hand the Module to honest-design's render and return the four-column Diagram it drew, unchanged.
    honest-render never recomputes column placement or edges; this pull is the only way it obtains the
    layout. honest-design's render is total and reports no fault."""
    return honest_design.render(module)


# --- the pure core: the section builders ----------------------------------------------------------
#
# build_view runs the section builders in rendering order through the _SECTION_BUILDERS table.
# Each section carries the lines or rows its kind declares.

# Render one type-part list (honest-design's bare union of named parts with args) as readable text, for
# example 'str', 'dict[str, str]', 'str | Fault'. The arg-bearing and bare cases are a two-row table.
_type_text = lambda parts: " | ".join(_part_text(part) for part in parts)
_part_text = lambda part: _pick(
    bool(part["args"]),
    lambda: f"{part['name']}[{', '.join(_type_text(arg) for arg in part['args'])}]",
    lambda: part["name"],
)

# The module note as opening prose, or the omitted marker when the declaration states none (section 5,
# 'Nothing invented'): a missing note is marked omitted, never guessed.
_note_line = lambda note: _pick(bool(note), lambda: note, lambda: _OMITTED)

# The module heading section: name, layer, version as prose, and the module note as opening prose.
_heading_section = lambda module, diagram: {
    "heading": module["name"],
    "kind": "heading",
    "lines": [
        f"name: {module['name']}",
        f"layer: {module['layer']}",
        f"version: {_note_line(module['version'])}",
        _note_line(module["note"]),
    ],
    "rows": [],
}

# The world section: the declared inputs and outputs, each with the family path honest-design assigns
# its kind, as prose lines.
_world_section = lambda module, diagram: {
    "heading": "World",
    "kind": "world",
    "lines": [f"reads {s['value']}: {s['description']}" for s in module["inputs"]]
    + [f"writes {s['value']}: {s['description']}" for s in module["outputs"]],
    "rows": [],
}

# One function's signature line: role, name, params and return type.
_signature = lambda function: (
    f"{function['role']}: {function['name']}("
    + ", ".join(f"{p['name']}: {_type_text(p['type'])}" for p in function["params"])
    + f") -> {_type_text(function['ret'])}"
)

# The invokes line when the function calls others, else nothing: a two-row table, no filter.
_invokes_lines = lambda function: _pick(
    bool(function["invokes"]),
    lambda: ["invokes: " + ", ".join(function["invokes"])],
    lambda: [],
)

# The awaited marker when the function is awaited, else nothing: a two-row table.
_awaited_lines = lambda function: _pick(function["awaited"], lambda: ["awaited"], lambda: [])

# One function shown whole as prose: its column placement, signature, invokes, the sides it touches,
# awaited, and its note (omitted when absent).
_function_lines = lambda column_title, function: (
    [f"[{column_title}] {function['name']}", _signature(function)]
    + _invokes_lines(function)
    + [f"{se['direction']} {se['target']}" for se in function["side_effects"]]
    + _awaited_lines(function)
    + [_note_line(function["note"])]
)

# The functions section: each function grouped and placed by the Diagram's columns, shown whole as
# prose. Column placement comes from the Diagram; the per-function detail comes from the Module.
_functions_section = lambda module, diagram: {
    "heading": "Functions",
    "kind": "functions",
    "lines": [
        line
        for column in diagram["columns"]
        for node in column["nodes"]
        for line in _function_lines(
            column["title"], {f["name"]: f for f in module["functions"]}[node["name"]]
        )
    ],
    "rows": [],
}

# The types table: each type with its fields and their types.
_types_section = lambda module, diagram: {
    "heading": "Types",
    "kind": "types",
    "lines": [],
    "rows": [["Type", "Field", "Type"]]
    + [
        [type_decl["name"], field["name"], _type_text(field["type"])]
        for type_decl in module["types"]
        for field in type_decl["record"]
    ],
}

# The sets table: each set with its members.
_sets_section = lambda module, diagram: {
    "heading": "Sets",
    "kind": "sets",
    "lines": [],
    "rows": [["Set", "Member"]]
    + [
        [set_decl["name"], member["value"]]
        for set_decl in module["sets"]
        for member in set_decl["members"]
    ],
}

# The vocabularies table: each vocabulary with the sets it draws on.
_vocabularies_section = lambda module, diagram: {
    "heading": "Vocabularies",
    "kind": "vocabularies",
    "lines": [],
    "rows": [["Vocabulary", "Sets"]]
    + [[vocab["name"], ", ".join(vocab["sets"])] for vocab in module["vocabularies"]],
}

# inherits: hd=python/honest-render/honest-render.hd::_dispatches_section -> feature=specs/features/honest-render.feature::_dispatches_section preserves dispatch and entry order -> test=python/honest-render/conformance/laws_dispatches_section_entry_order.py::probe_dispatches_section_entry_order
# inherits: hd=python/honest-render/honest-render.hd::_dispatches_section -> feature=specs/features/honest-render.feature::_dispatches_section keeps only the header when there are no entries -> test=python/honest-render/conformance/laws_dispatches_section_no_entries.py::probe_dispatches_section_no_entries
# hd: _dispatches_section
def _dispatches_section(module, diagram):
    """Project dispatch entries into ordered key and handler rows."""
    return {
        "heading": "Dispatches",
        "kind": "dispatches",
        "lines": [],
        "rows": [["Dispatch", "Key", "Target"]]
        + [
            [dispatch["name"], entry["key"], entry["handler"]]
            for dispatch in module["dispatches"]
            for entry in dispatch["entries"]
        ],
    }


# inherits: hd=python/honest-render/honest-render.hd::_chains_section -> feature=specs/features/honest-render.feature::_chains_section keeps separate directed edges in diagram order -> test=python/honest-render/conformance/laws_chains_section_directed_edges.py::probe_chains_section_directed_edges
# inherits: hd=python/honest-render/honest-render.hd::_chains_section -> feature=specs/features/honest-render.feature::_chains_section shows a standalone link and does not infer missing edges -> test=python/honest-render/conformance/laws_chains_section_missing_edges.py::probe_chains_section_missing_edges
# hd: _chains_section
def _chains_section(module, diagram):
    """Keep each declared chain's directed diagram pairs in supplied order."""
    lines = []
    for chain in module["chains"]:
        name = chain["name"]
        edges = filter(lambda edge: edge["chain"] == name, diagram["edges"])
        pairs = [f"{edge['src']} -> {edge['dst']}" for edge in edges]
        links = chain["links"]
        visible = pairs or _pick(len(links) == 1, lambda: links, lambda: [])
        lines.append(_pick(bool(visible), lambda: f"{name}: {', '.join(visible)}", lambda: name))
    return {"heading": "Chains", "kind": "chains", "lines": lines, "rows": []}


# inherits: hd=python/honest-render/honest-render.hd::_routes_section -> feature=specs/features/honest-render.feature::_routes_section keeps headerless route rows in declaration order -> test=python/honest-render/conformance/laws_routes_section_headerless_rows.py::probe_routes_section_headerless_rows
# hd: _routes_section
def _routes_section(module, diagram):
    """Keep the declared route rows in order."""
    return {
        "heading": "Routes",
        "kind": "routes",
        "lines": [],
        "rows": [[route["method"], route["path"], route["target"]] for route in module["routes"]],
    }


# inherits: hd=python/honest-render/honest-render.hd::_entries_section -> feature=specs/features/honest-render.feature::_entries_section keeps headerless entry rows in declaration order -> test=python/honest-render/conformance/laws_entries_section_headerless_rows.py::probe_entries_section_headerless_rows
# hd: _entries_section
def _entries_section(module, diagram):
    """Keep the declared entry rows in order."""
    return {
        "heading": "Entries",
        "kind": "entries",
        "lines": [],
        "rows": [[entry["callsite"], entry["target"]] for entry in module["entries"]],
    }


# The exposes/surfaces/examples sections are one shape: a prose list of the items in a named Module
# list. Each is bound once in the builders table below with its own heading, kind and the list it reads,
# so there is one recognizer, not three near-identical functions (HC-P014), and no variable-key subscript
# (HC-P020): the kind and heading are literals at the binding site.
_list_section = lambda heading, kind, items: {
    "heading": heading,
    "kind": kind,
    "lines": [str(item) for item in items],
    "rows": [],
}


# The ordered, closed table of section builders in rendering order (section 4). build_view runs each one
# unconditionally, so the set of kinds and their order are data, not an if ladder: an empty grouping
# renders as a table with only its header or a list with no items, never a dropped section. Each builder
# is (module, diagram) -> ViewSection.
_SECTION_BUILDERS = [
    _heading_section,
    _world_section,
    _functions_section,
    _types_section,
    _sets_section,
    _vocabularies_section,
    _dispatches_section,
    _chains_section,
    _routes_section,
    _entries_section,
    lambda module, diagram: _list_section("Exposes", "exposes", module["exposes"]),
    lambda module, diagram: _list_section("Surfaces", "surfaces", module["surfaces"]),
    lambda module, diagram: _list_section("Examples", "examples", module["examples"]),
]


# inherits: hd=python/honest-render/honest-render.hd::build_view -> feature=specs/features/honest-render.feature::build_view -> test=python/honest-render/conformance/laws_build_view.py::probe_build_view
# inherits: hd=python/honest-render/honest-render.hd::build_view -> feature=specs/features/honest-render.feature::build_view uses supplied diagram edges for the chain layout -> test=python/honest-render/conformance/laws_build_view_diagram_edges.py::probe_build_view_diagram_edges
# inherits: hd=python/honest-render/honest-render.hd::build_view -> feature=specs/features/honest-render.feature::build_view preserves declared facts in ordered view sections -> test=python/honest-render/conformance/laws_build_view_ordered_sections.py::probe_build_view_ordered_sections
# hd: build_view
def build_view(module, diagram):
    """Turn honest-design's Module and Diagram into a ViewModel: the declaration reorganized into the
    order and groupings a reader wants. It decides structure, not text, and invents nothing the
    declaration does not state. Column placement and edges come from the diagram; every other fact
    comes from the module. Pure: it reads no world."""
    sections = [build(module, diagram) for build in _SECTION_BUILDERS]
    return {"module_name": module["name"], "sections": sections}


# --- the pure Markdown renderer -------------------------------------------------------------------

# A prose section: a level-2 heading, then each line as its own paragraph.
_render_prose = lambda section: "\n\n".join([f"## {section['heading']}"] + section["lines"])

# One pipe-delimited Markdown row, and the header divider under it.
_header_line = lambda cells: "| " + " | ".join(cells) + " |"
_divider_line = lambda header: "| " + " | ".join("---" for _ in header) + " |"

# The table lines for a rows list: header, divider, then each data row; an empty rows list yields no
# lines. A two-row table on whether rows is non-empty (HC-P001), not an if.
_table_body = lambda rows: _pick(
    bool(rows),
    lambda: [_header_line(rows[0]), _divider_line(rows[0])]
    + [_header_line(row) for row in rows[1:]],
    lambda: [],
)

# A table section: a level-2 heading, a blank line, then the rows as a pipe-delimited table whose first
# row is the header.
_render_table = lambda section: "\n".join(
    [f"## {section['heading']}", ""] + _table_body(section["rows"])
)


# inherits: hd=python/honest-render/honest-render.hd::_render_ordered_list -> feature=specs/features/honest-render.feature::_render_ordered_list numbers chain lines in supplied order -> test=python/honest-render/conformance/laws_render_ordered_list_chain_lines.py::probe_render_ordered_list_chain_lines
# inherits: hd=python/honest-render/honest-render.hd::_render_ordered_list -> feature=specs/features/honest-render.feature::_render_ordered_list leaves only the heading for an empty section -> test=python/honest-render/conformance/laws_render_ordered_list_empty_section.py::probe_render_ordered_list_empty_section
# inherits: hd=python/honest-render/honest-render.hd::_render_ordered_list -> feature=specs/features/honest-render.feature::_render_ordered_list numbers route and entry rows without table syntax -> test=python/honest-render/conformance/laws_render_ordered_list_route_entry_rows.py::probe_render_ordered_list_route_entry_rows
# hd: _render_ordered_list
def _render_ordered_list(section):
    """Render one numbered Markdown item per chain line or route or entry row."""
    items = section["lines"] + [" ".join(row) for row in section["rows"]]
    heading = f"## {section['heading']}"
    numbered = "\n".join(f"{number}. {item}" for number, item in enumerate(items, start=1))
    return _pick(bool(items), lambda: f"{heading}\n\n{numbered}", lambda: heading)


# Each section_kind renders as prose, a table, or a list. A closed table keyed on the bounded section_kinds
# vocabulary (build_view tags each section with one of these), so an unknown kind cannot be read as a
# handled one; the read is by subscript, and the key can only come from the closed vocabulary (P16).
_SECTION_RENDERERS = {
    "heading": _render_prose,
    "world": _render_prose,
    "functions": _render_prose,
    "chains": _render_ordered_list,
    "exposes": _render_prose,
    "surfaces": _render_prose,
    "examples": _render_prose,
    "types": _render_table,
    "sets": _render_table,
    "vocabularies": _render_table,
    "dispatches": _render_table,
    "routes": _render_ordered_list,
    "entries": _render_ordered_list,
}


# inherits: hd=python/honest-render/honest-render.hd::render_markdown -> feature=specs/features/honest-render.feature::render_markdown -> test=python/honest-render/conformance/laws_render_markdown.py::probe_render_markdown
# inherits: hd=python/honest-render/honest-render.hd::render_markdown -> feature=specs/features/honest-render.feature::render_markdown renders routes and entries as ordered lists -> test=python/honest-render/conformance/laws_render_markdown_ordered_lists.py::probe_render_markdown_ordered_lists
# inherits: hd=python/honest-render/honest-render.hd::render_markdown -> feature=specs/features/honest-render.feature::render_markdown matches the stored rich Markdown fixture byte for byte -> test=python/honest-render/conformance/laws_render_markdown_rich_fixture.py::probe_render_markdown_rich_fixture
# hd: render_markdown
def render_markdown(view):
    """Turn the ViewModel into the Markdown document string: the module heading and note as prose, a
    function shown whole as prose, the types/sets/vocabularies/dispatches as tables, the
    chains/routes/entries as lists. Deterministic: the same ViewModel renders to byte-identical
    Markdown every time, with no clock and no external state. Pure: it reads no world."""
    blocks = [f"# {view['module_name']}"] + [
        _SECTION_RENDERERS[section["kind"]](section) for section in view["sections"]
    ]
    return "\n\n".join(blocks) + "\n"


# --- the output boundary --------------------------------------------------------------------------


# The destination path resolved for the write: a real file path to open, or the process stdout stream
# when the OutputTarget chose NOTHING. A two-row table on whether path is NOTHING selects the stream, so
# the boundary opens one target and writes once, with no if and no second I/O site (P01, P12).
_write_target = lambda path: _pick(
    path is None,
    lambda: contextlib.nullcontext(sys.stdout),
    lambda: open(path, "w", encoding="utf-8"),
)


# hd: write_document
def write_document(document, output):
    """Write the document to exactly one side, chosen by output.path: a path string writes to that file
    (file:given), NOTHING (None) writes to standard output (stdout). Thin: it builds no Fault. ok true
    with empty detail on a clean write; ok false with the write error in detail on a failure. The side
    choice is a two-row table on whether path is NOTHING, not an if (HC-P001); the handle closes within
    the with-scope (stdout stays open via nullcontext), and the OS error is caught here and reported as
    data, never a raise."""
    try:
        with _write_target(output["path"]) as handle:
            handle.write(document)
        return {"ok": True, "detail": ""}
    except OSError as exc:
        return {"ok": False, "detail": str(exc)}


# --- the orchestrator -----------------------------------------------------------------------------

# The orchestrator's write decision: the document on a clean write, the write_failed Fault on a failure.
# A two-row table on the WriteOutcome's ok, mirroring honest-observe's _emit_outcome. render_fault is
# called forward (orchestrator -> pure) with the write_failed row from _FAULT_WORDS, so there is one
# builder over the table and not a second shape-identical fault function (HC-P014).
_after_write = lambda document, write_outcome: _pick(
    write_outcome["ok"],
    lambda: document,
    lambda: render_fault(
        code="write_failed",
        category=_FAULT_WORDS["write_failed"]["category"],
        message=_FAULT_WORDS["write_failed"]["message"],
        detail={"write_error": write_outcome["detail"]},
    ),
)


# hd: render_declaration
def render_declaration(request):
    """Compose the work above the pure core and own all fault construction. Pull the file text; on a
    failed read build a file_unreadable client Fault via render_fault. On a clean read pull the Module
    (read_ir) and, when it is a Fault -- either a passed-through read_hd fault or the client
    not_single_module fault read_ir built -- pass it through unchanged and render nothing (section 3b).
    Otherwise draw the diagram, drive the two pure steps, and write; on a failed write build a
    write_failed server Fault. On a clean write return the document string. Every fault comes back as
    data, never raised; each decision is a closed two-row table (P01)."""

    def _render_and_write(module):
        # A valid single Module in hand: draw the diagram, build the view, render the Markdown, write
        # it, and return the document or the write_failed Fault.
        diagram = draw_diagram(module)
        document = render_markdown(build_view(module, diagram))
        return _after_write(document, write_document(document, request["output"]))

    def _after_read_ir(module_or_fault):
        # read_ir returned either a Fault (a passed-through read_hd fault or the not_single_module
        # fault) or the one Module. Pass any Fault through unchanged; otherwise render and write.
        return _pick(
            is_fault(module_or_fault),
            lambda: module_or_fault,
            lambda: _render_and_write(module_or_fault),
        )

    def _after_read_source(read_outcome):
        # Build the file_unreadable client Fault on a failed read, or obtain the Module via read_ir
        # and continue. A two-row table on the ReadOutcome's ok (P01).
        return _pick(
            read_outcome["ok"],
            lambda: _after_read_ir(read_ir(read_outcome["text"])),
            lambda: render_fault(
                code="file_unreadable",
                category=_FAULT_WORDS["file_unreadable"]["category"],
                message=_FAULT_WORDS["file_unreadable"]["message"],
                detail={"read_error": read_outcome["detail"]},
            ),
        )

    return _after_read_source(read_source(request["hd_path"]))


# --- the door -------------------------------------------------------------------------------------

# hd: render_file
def render_file(request):
    """The single input boundary, the one door honest-render presents. It accepts a RenderRequest and
    hands it to exactly one orchestrator, render_declaration, adding nothing of its own. It returns the
    rendered document string on success, or honest-render's Fault as data when the render failed. The
    fault travels back here by return; the door is never where it is raised."""
    return render_declaration(request)
