# scenario: render_markdown
"""honest-render render_markdown law: the second pure step turns a ViewModel into the
Markdown document string, deciding text and not structure. This fragment is data-driven
and pure: it builds ViewModel inputs as plain data (plain dicts, no test-double class,
no default kwargs anywhere -- every ViewSection field is written out in full, and an
empty lines/rows is the literal []), calls the REAL render_markdown (no mock, no
stand-in), and returns a list of failure strings (empty when the case holds).

What the scenario (specs/features/honest-render.feature, render_markdown) fixes, and so
what this fragment pins:
  - it turns each ViewSection into Markdown: the module heading and note as PROSE, a
    function shown whole as prose with its signature, the types/sets/vocabularies/
    dispatches as Markdown TABLES, the chains/routes/entries as Markdown LISTS;
  - it is DETERMINISTIC: the same ViewModel renders to byte-identical Markdown every
    time, with no clock and no external state, so a repeat render produces identical
    output;
  - it is pure: it reads no world, so the input alone determines the output.

The scenario does NOT fix the exact Markdown string, the heading markup level, the exact
table/list syntax, or the ordering markup; those are gaps owned by the layer above. So the
non-trivial cases pin only what the scenario states in kind -- that the heading/note text,
the table cell text, and the list item text each surface in the output, and that a table
section surfaces as a pipe-delimited table -- never an invented exact string. The
determinism case pins byte-identity, which the scenario states outright.

A stub body `return ""` fails every non-trivial case here (the required text is absent),
so this probe is not vacuous.
"""

from honest_render import render_markdown


# A ViewModel is {module_name: str, sections: list[ViewSection]}; a ViewSection is
# {heading, kind, lines, rows}. Every section below is a plain dict with ALL FOUR fields
# written out explicitly -- a prose section states rows as the literal [], a table section
# states lines as the literal [] -- so nothing is defaulted and the two sides of each
# check are built independently of the function under test.

_HEADING_SECTION = {
    "heading": "honest-widget",
    "kind": "heading",
    "lines": ["the public widget renderer that turns one declaration into a page"],
    "rows": [],
}

_TYPES_SECTION = {
    "heading": "Types",
    "kind": "types",
    "lines": [],
    "rows": [
        ["Field", "Type"],
        ["widget_id", "str"],
        ["enabled", "bool"],
    ],
}

_CHAINS_SECTION = {
    "heading": "Chains",
    "kind": "chains",
    "lines": ["render_pipeline: render_file -> render_declaration"],
    "rows": [],
}

_VIEW = {
    "module_name": "honest-widget",
    "sections": [_HEADING_SECTION, _TYPES_SECTION, _CHAINS_SECTION],
}


def _law_contains_heading_and_note():
    """The heading section's heading and its note line render into the document as prose."""
    bad = []
    out = render_markdown(view=_VIEW)
    if not isinstance(out, str):
        return [f"render_markdown returned {type(out).__name__}, expected str"]
    if "honest-widget" not in out:
        bad.append(
            "render_markdown output missing the module heading text 'honest-widget'"
        )
    note = "the public widget renderer that turns one declaration into a page"
    if note not in out:
        bad.append(f"render_markdown output missing the heading-note prose {note!r}")
    return bad


def _law_types_render_as_table():
    """The types section renders as a Markdown table: its cell text surfaces, and the
    pipe-delimited table syntax appears in the output."""
    bad = []
    out = render_markdown(view=_VIEW)
    if not isinstance(out, str):
        return [f"render_markdown returned {type(out).__name__}, expected str"]
    for cell in ("widget_id", "str", "enabled", "bool"):
        if cell not in out:
            bad.append(f"render_markdown output missing types-table cell {cell!r}")
    if "|" not in out:
        bad.append(
            "render_markdown output has no '|' -- the types section was not rendered "
            "as a Markdown table"
        )
    return bad


def _law_chains_render_as_list():
    """The chains section renders as a Markdown list: its item text surfaces in the output."""
    bad = []
    out = render_markdown(view=_VIEW)
    if not isinstance(out, str):
        return [f"render_markdown returned {type(out).__name__}, expected str"]
    item = "render_pipeline: render_file -> render_declaration"
    if item not in out:
        bad.append(f"render_markdown output missing chains-list item {item!r}")
    return bad


def _law_deterministic():
    """A repeat render of the same ViewModel yields byte-identical output (scenario: it is
    deterministic, with no clock and no external state)."""
    bad = []
    first = render_markdown(view=_VIEW)
    second = render_markdown(view=_VIEW)
    if first != second:
        bad.append(
            "render_markdown is not deterministic: two renders of the same ViewModel "
            f"differ -- first={first!r} second={second!r}"
        )
    # Byte-identity, stated explicitly, over an independently-built equal ViewModel whose
    # sections are each written out in full with no defaulted field.
    twin = {
        "module_name": "honest-widget",
        "sections": [
            {
                "heading": "honest-widget",
                "kind": "heading",
                "lines": [
                    "the public widget renderer that turns one declaration into a page"
                ],
                "rows": [],
            },
            {
                "heading": "Types",
                "kind": "types",
                "lines": [],
                "rows": [
                    ["Field", "Type"],
                    ["widget_id", "str"],
                    ["enabled", "bool"],
                ],
            },
            {
                "heading": "Chains",
                "kind": "chains",
                "lines": ["render_pipeline: render_file -> render_declaration"],
                "rows": [],
            },
        ],
    }
    third = render_markdown(view=twin)
    if not isinstance(first, str) or not isinstance(third, str):
        return bad + ["render_markdown returned a non-str, expected str"]
    if first.encode("utf-8") != third.encode("utf-8"):
        bad.append(
            "render_markdown is not byte-identical across equal ViewModels: "
            f"first={first!r} third={third!r}"
        )
    return bad


def _law_empty_model_is_nonrandom():
    """The absence case: a ViewModel with no sections renders deterministically. The
    scenario does not fix the exact empty-document text, so this case pins only that two
    renders of the empty model agree (determinism holds at the boundary too), never an
    invented string. The sections list is the literal [], written out, never defaulted."""
    bad = []
    empty = {"module_name": "honest-widget", "sections": []}
    a = render_markdown(view=empty)
    b = render_markdown(view=empty)
    if not isinstance(a, str):
        return [f"render_markdown(empty) returned {type(a).__name__}, expected str"]
    if a != b:
        bad.append(
            "render_markdown on an empty-section ViewModel is not deterministic: "
            f"a={a!r} b={b!r}"
        )
    return bad


_LAWS = [
    _law_contains_heading_and_note,
    _law_types_render_as_table,
    _law_chains_render_as_list,
    _law_deterministic,
    _law_empty_model_is_nonrandom,
]


def probe_render_markdown():
    """render_markdown turns each ViewSection into Markdown -- heading and note as prose,
    types as a table, chains as a list -- and is deterministic: the same ViewModel renders
    to byte-identical Markdown every time."""
    bad = []
    for law in _LAWS:
        bad.extend(law())
    return bad


if __name__ == "__main__":
    import sys

    failures = probe_render_markdown()
    if failures:
        print(f"RED: probe_render_markdown found {len(failures)} failure(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("GREEN: probe_render_markdown found no failures")
