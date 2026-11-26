# scenario: build_view
"""honest-render build_view: the first pure step. It takes honest-design's Module and Diagram and
produces a ViewModel -- the declaration reorganized into the order and groupings a reader wants.

Honest test, not a mock test. The two inputs are foreign honest-design types (Module, Diagram), and
honest-design is a REAL built dependency: this probe runs honest-design's own read_hd and render over
a real .hd source to obtain a genuine Module and a genuine Diagram, then calls the REAL build_view on
them. Nothing about honest-design is stood in for; the only function under test, and the only thing
that may be absent, is honest_render.build_view.

What the scenario fixes, and what this probe pins:
  - module_name is the name of the module, taken from the Module (literal, non-trivial: "honest-render").
    A stub returning {"module_name": "", "sections": []} fails this case.
  - build_view builds ViewSections tagging each with its SectionKind from the CLOSED section_kinds set,
    and the heading section carries the module name/layer/version and the module note as opening prose.
  - absence case: a module whose note is missing is marked omitted, never guessed -- build_view must not
    fabricate note prose the declaration does not state.
"""

from pathlib import Path

import honest_design as _HD

from honest_render import build_view  # the REAL function under test; absent -> expected red (ImportError)


# The closed section_kinds set honest-render declares (honest-render.hd, section_kinds).
_SECTION_KINDS = frozenset(
    {
        "heading",
        "world",
        "functions",
        "types",
        "sets",
        "vocabularies",
        "dispatches",
        "chains",
        "routes",
        "entries",
        "exposes",
        "surfaces",
        "examples",
    }
)

# A real .hd that honest-design parses cleanly, carrying a module note.
_SRC_WITH_NOTE = (Path(__file__).resolve().parents[1] / "honest-render.hd").read_text(encoding="utf-8")


def _real_module(source):
    """Obtain a genuine honest-design Module from source text via the REAL read_hd (no mock)."""
    res = _HD.read_hd(source)
    mod = res["ok"] if isinstance(res, dict) and "ok" in res else res
    return mod["modules"][0]


def _real_diagram(module):
    """Obtain a genuine honest-design Diagram from the Module via the REAL render (no mock)."""
    return _HD.render(module)


def _module_without_note(module):
    """The same real Module with its note removed: the explicit absence row the scenario names
    ('a missing note is marked omitted, never guessed'). Everything else is the real declaration."""
    stripped = dict(module)
    stripped["note"] = ""
    return stripped


def _heading_section(view):
    for sec in view.get("sections", []):
        if sec.get("kind") == "heading":
            return sec
    return None


def probe_build_view():
    """build_view turns honest-design's Module and Diagram into a ViewModel whose module_name is the
    Module's name, whose sections are tagged with kinds from the closed section_kinds set, whose
    heading section opens with the module note, and which marks a missing note omitted, never guessed."""
    bad = []

    module = _real_module(_SRC_WITH_NOTE)
    diagram = _real_diagram(module)
    expected_name = module["name"]  # the real module name honest-design read: "honest-render"
    note_text = module["note"]

    view = build_view(module=module, diagram=diagram)

    # 1. module_name is the name taken from the Module -- literal, non-trivial (fails an empty stub).
    got_name = view.get("module_name")
    if got_name != expected_name:
        bad.append(
            f"build_view(...).module_name -> {got_name!r}, expected the Module's name {expected_name!r}"
        )

    # 2. there is at least one section, each tagged with a kind from the closed section_kinds set.
    sections = view.get("sections")
    if not sections:
        bad.append("build_view(...).sections is empty; the ViewModel must carry the declaration's sections")
    else:
        for i, sec in enumerate(sections):
            kind = sec.get("kind")
            if kind not in _SECTION_KINDS:
                bad.append(
                    f"build_view(...).sections[{i}].kind -> {kind!r}, not in the closed section_kinds set"
                )

    # 3. the heading section exists and opens with the module note as prose (the declaration states it).
    heading = _heading_section(view)
    if heading is None:
        bad.append("build_view(...) has no section with kind 'heading'; the module heading must be rendered")
    else:
        lines = heading.get("lines") or []
        if note_text and not any(note_text in line for line in lines):
            bad.append(
                f"build_view(...) heading section does not carry the module note {note_text!r} in its lines"
            )

    # 4. absence case: a module whose note is missing is marked omitted, never guessed.
    module_no_note = _module_without_note(module)
    diagram_no_note = _real_diagram(module_no_note)
    view_no_note = build_view(module=module_no_note, diagram=diagram_no_note)
    heading_no_note = _heading_section(view_no_note)
    if heading_no_note is None:
        bad.append("build_view(...) on a note-less module has no heading section")
    else:
        lines = heading_no_note.get("lines") or []
        if note_text and any(note_text in line for line in lines):
            bad.append(
                "build_view(...) on a note-less module fabricated the original note text; a missing note "
                "must be marked omitted, never guessed"
            )

    return bad


if __name__ == "__main__":
    failures = probe_build_view()
    if failures:
        print(f"RED: {len(failures)} failure(s)")
        for f in failures:
            print(" -", f)
        raise SystemExit(1)
    print("GREEN")
