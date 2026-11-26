Feature: honest-render — Rendering contracts

  # hd: python/honest-render/honest-render.hd::render_file
  Scenario: render_file is available as an honest_render public export
    Given the installed honest_render Python package
    When the host inspects the package's public exports
    Then the literal __all__ lists exactly render_file, in any order
    And render_file resolves to a callable attribute of honest_render
    And existing package bindings outside __all__ remain available through explicit named imports

  Scenario: render_file
    Given request: RenderRequest
    When render_file is called
    Then it is the single input boundary, the one door honest-render presents, and it accepts the RenderRequest carrying the .hd path and the chosen OutputTarget
    And it checks its own input, because a boundary cannot assume the caller's types, then hands the request to exactly one orchestrator, render_declaration, and adds nothing of its own
    And it returns the rendered document as a string on success, the same bytes the output boundary wrote, answered to the caller
    And it returns honest-render's Fault when honest-design's read_hd reported the .hd is malformed or is not a valid declaration, in which case no document is rendered
    And the fault travels back here by return from the orchestrator as data, never raised
    And it is the function named on the entry "export honest_render" so the world has a named way in

  Scenario: read_source
    Given hd_path: str
    When read_source is called
    Then it is the reader on the filesystem side, honest-render's only input side effect, and it reads the .hd file's text from the filesystem (side file:given, the OS/persistence file family at a path known only at run time)
    And it stays thin and builds no Fault
    And on a clean read it returns a ReadOutcome with ok true and the complete file text in text and empty detail
    And on a failed read (file_unreadable condition: the .hd path could not be read) it returns a ReadOutcome with ok false, empty text, and the read error in detail, so the orchestrator can build the file_unreadable Fault
    And it does not parse, render, write, or construct a Fault; fault construction is the orchestrator's

  Scenario: write_document
    Given document: str and output: OutputTarget
    When write_document is called
    Then it is the output boundary, honest-render's only output side effect, and it writes the rendered document bytes the pure core produced to exactly one of two sides per call, never both
    And when output.path is a path string it writes the document to the file at that path (the file:given side, a destination path known only at run time)
    And when output.path is NOTHING it writes the document to standard output (the stdout side, the console stdout family)
    And it stays thin and builds no Fault
    And on a clean write it returns a WriteOutcome with ok true and empty detail
    And on a failed write (write_failed condition: the destination could not be written) it returns a WriteOutcome with ok false and the write error in detail, so the orchestrator can build the write_failed Fault
    And it does not parse, build, render, or construct a Fault; fault construction is the orchestrator's

  # hd: python/honest-render/honest-render.hd::render_declaration
  Scenario: render_declaration
    Given request: RenderRequest
    When render_declaration is called
    Then it is the one orchestrator, composing the work above the pure core and owning all fault construction, and it raises nothing: every fault case comes back as the Fault value as data
    And it pulls the .hd file text with read_source, which returns a ReadOutcome
    And when the read outcome is not ok it builds a file_unreadable Fault via render_fault, with category client and detail.read_error equal to the reader outcome's detail, and returns it, rendering nothing
    And the read-failure message explains that the .hd path could not be read and gives a useful next action
    And on a clean read it passes the outcome's text to honest-design: the Module from read_ir (honest-design's read_hd) and the Diagram from draw_diagram (honest-design's render), performing no parse and no column computation of its own
    And if read_ir returns honest-render's Fault (honest-design's read_hd reported the .hd is malformed or is not a valid declaration) it surfaces that fault as data and renders nothing, returning it to the door with its own code, message and category unchanged, never re-wrapped
    And on a valid declaration it drives build_view to turn the Module and Diagram into a ViewModel, then render_markdown to turn the ViewModel into the Markdown document string
    And it hands the document and the request's OutputTarget to write_document, which returns a WriteOutcome
    And when the write outcome is not ok it builds a write_failed Fault via render_fault, with category server and detail.write_error equal to the writer outcome's detail, and returns it
    And the write-failure message explains that the destination could not be written and gives a useful next action
    And on a clean write it returns the rendered document string

  # hd: python/honest-render/honest-render.hd::read_ir
  Scenario: read_ir
    Given source: str
    When read_ir is called
    Then it is the import seam to honest-design's read path, honest-render's side of import honest_design for the Module (side it reads: honest-design.read_hd)
    And it hands the complete .hd source text to honest-design's read_hd and returns the Module intermediate representation honest-design read on a valid declaration
    And it returns honest-render's Fault when read_hd reported the .hd is malformed or is not a valid declaration, carried back by return as a bare union arm so the orchestrator can surface it and render nothing
    And a Document containing zero or two modules returns a bare not_single_module client Fault whose is_err tag is true, whose detail reports the observed count, and whose message explains the one-module requirement and how to correct the declaration
    And honest-render never parses .hd itself; this pull is the only way it obtains a Module

  # hd: python/honest-render/honest-render.hd::read_ir
  # spec: Honest Render §3b (as cited by the declaration)
  Scenario: read_ir asks the caller to supply one module when none are declared
    Given source: str is a valid declaration document containing no modules
    When read_ir is called
    Then it returns a bare Fault with is_err true, code not_single_module, category client and detail.module_count equal to the string "0"
    And the message explains that no module was declared and asks the caller to supply one module

  # hd: python/honest-render/honest-render.hd::read_ir
  # spec: Honest Render §3b (as cited by the declaration)
  Scenario: read_ir asks the caller to render multiple declared modules individually
    Given source: str is a valid declaration document containing two modules
    When read_ir is called
    Then it returns a bare Fault with is_err true, code not_single_module, category client and detail.module_count equal to the string "2"
    And the message explains that multiple modules were declared and asks the caller to render them individually

  Scenario: draw_diagram
    Given module: Module
    When draw_diagram is called
    Then it is the import seam to honest-design's static renderer, honest-render's side of import honest_design for the Diagram (side it reads: honest-design.render)
    And it hands the Module to honest-design's render and returns the four-column Diagram honest-design drew, the column-placed nodes and the chain edges
    And honest-design's render is total and reports no fault, so this pull carries none
    And honest-render never recomputes column placement or edges; this pull is the only way it obtains the layout

  Scenario: build_view
    Given module: Module and diagram: Diagram
    When build_view is called
    Then it is the first pure step, building the document view, and it decides structure, not text
    And it takes honest-design's Module and Diagram and produces a ViewModel: the declaration reorganized into the order and groupings a reader wants
    And column placement and edges come from the diagram (each function grouped and placed in the column the diagram gives and the chain edges the diagram gives) and the per-declaration detail (notes, signatures, invokes, the type/set/vocabulary/dispatch tables, the chains, routes, entries, exposes, surfaces, examples) comes from the module
    And it builds the ViewSections in rendering order, tagging each with its SectionKind from the closed section_kinds set, carrying prose in lines and tables in rows
    And it invents nothing the declaration does not state: a missing note is marked omitted, never guessed
    And it is pure: it reads no world and produces the ViewModel from its two inputs alone

  # hd: python/honest-render/honest-render.hd::build_view
  # spec: Honest Render §§4 and 5 (as cited by the declaration)
  Scenario: build_view preserves declared facts in ordered view sections
    Given module: Module is parsed from a synthetic declaration with a name, layer, version, note, input and output specifications, functions, types, sets, vocabularies, dispatches, chains, routes, entries, exposes, surfaces and examples
    And diagram: Diagram supplies the placed functions and directed chain edges
    When build_view is called
    Then it returns a ViewModel with module_name and sections ordered as heading, world, functions, types, sets, vocabularies, dispatches, chains, routes, entries, exposes, surfaces and examples
    And each ViewSection carries its heading, kind, lines and rows, with prose in lines and tabular cells or ordered records in rows as its kind requires
    And it retains the module name, layer, version and authored note, and the world sides with their direction, family paths and descriptions
    And it shows each function in the supplied diagram column with its role, full parameter and return types including unions, invokes, side effects, awaited status and authored note
    And it preserves the declared table cells, ordered route and entry fields, chain names and supplied Diagram edges, and declared exposes, surfaces and examples
    And a missing note is marked omitted instead of supplying an explanation

  # hd: python/honest-render/honest-render.hd::build_view
  # spec: Honest Render §§4 and 5 (as cited by the declaration)
  Scenario: build_view uses supplied diagram edges for the chain layout
    Given module: Module declares a chain and names its functions and diagram: Diagram places those functions but supplies a different valid edge layout among them
    When build_view is called
    Then the chain layout follows the supplied Diagram edges and function placement
    And the declaration details still come from the Module and edges are not recomputed from its chain links

  Scenario: render_markdown
    Given view: ViewModel
    When render_markdown is called
    Then it is the second pure step, rendering the document view, and it decides text, not structure
    And it takes the ViewModel and produces the output document as a string: Markdown, the first and normative output format
    And it turns each ViewSection into Markdown: the module heading and note as prose, a function shown whole as prose with its signature, the types/sets/vocabularies/dispatches as Markdown tables, the chains/routes/entries as Markdown lists
    And it is deterministic: the same ViewModel renders to byte-identical Markdown every time, with no clock and no external state, so a repeat render of the same .hd produces byte-identical output
    And it is pure: it reads no world

  # hd: python/honest-render/honest-render.hd::render_markdown
  # spec: Honest Render §§5, 7, 8 and 9
  Scenario: render_markdown matches the stored rich Markdown fixture byte for byte
    Given view: ViewModel includes a module heading, two prose paragraphs, and types, sets, vocabularies and dispatches sections each with a header and data row
    And the view includes chain, route and entry sections with items in a fixed supplied order
    When render_markdown is called
    Then its Markdown equals the stored expected output for this ViewModel byte for byte
    And repeating the render returns the same bytes

  # hd: python/honest-render/honest-render.hd::render_markdown
  # spec: Honest Render §§5 and 8 (as cited by the declaration)
  Scenario: render_markdown renders routes and entries as ordered lists
    Given view: ViewModel contains two route rows and two entry rows in a fixed order
    When render_markdown is called
    Then it renders routes and entries as Markdown ordered lists in the same order
    And each route item preserves its method, path and target, and each entry item preserves its external callsite and target

  # hd: python/honest-render/honest-render.hd::_dispatches_section
  # spec: Honest Render §§4 and 5 (as cited by the declaration)
  Scenario: _dispatches_section preserves dispatch and entry order
    Given module: Module lists dispatch "second" with entries "z" to handler "send" and "a" to handler "start", followed by dispatch "first" with entry "m" to handler "move"
    And the "z" entry has projection metadata and diagram: Diagram supplies layout
    When _dispatches_section is called
    Then it returns the Dispatches section with kind dispatches, empty lines, and rows [["Dispatch", "Key", "Target"], ["second", "z", "send"], ["second", "a", "start"], ["first", "m", "move"]]

  # hd: python/honest-render/honest-render.hd::_dispatches_section
  # spec: Honest Render §§4 and 5 (as cited by the declaration)
  Scenario: _dispatches_section keeps only the header when there are no entries
    Given module: Module supplies no dispatch entries and diagram: Diagram supplies layout
    When _dispatches_section is called
    Then it returns the Dispatches section with kind dispatches, empty lines, and only the row ["Dispatch", "Key", "Target"]

  # hd: python/honest-render/honest-render.hd::_chains_section
  Scenario: _chains_section keeps separate directed edges in diagram order
    Given module: Module declares a chain named dispatch, and diagram: Diagram supplies separate dispatch edges from start to check and from send to finish in that order
    When _chains_section is called
    Then it returns one chains item named dispatch carrying the directed pairs start to check and send to finish in that order, without implying a check to send edge, and rows is empty

  # hd: python/honest-render/honest-render.hd::_chains_section
  Scenario: _chains_section shows a standalone link and does not infer missing edges
    Given module: Module declares chains named single, many and empty with one, multiple and zero links respectively, and diagram: Diagram supplies no edges for them
    When _chains_section is called
    Then it returns one chains item for each in declaration order, shows the one link for single, shows only the names for many and empty, and rows is empty

  # hd: python/honest-render/honest-render.hd::_routes_section
  Scenario: _routes_section keeps headerless route rows in declaration order
    Given module: Module declares GET /items to list_items then POST /items to create_item and diagram: Diagram supplies layout
    When _routes_section is called
    Then it returns the routes section with lines empty and exactly the rows [["GET", "/items", "list_items"], ["POST", "/items", "create_item"]]

  # hd: python/honest-render/honest-render.hd::_entries_section
  Scenario: _entries_section keeps headerless entry rows in declaration order
    Given module: Module declares cli:open to open_items then export:close to close_items and diagram: Diagram supplies layout
    When _entries_section is called
    Then it returns the entries section with lines empty and exactly the rows [["cli:open", "open_items"], ["export:close", "close_items"]]

  # hd: python/honest-render/honest-render.hd::_render_ordered_list
  Scenario: _render_ordered_list numbers chain lines in supplied order
    Given section: ViewSection is a chains section headed "Chains" with lines "first" and "second" in that order
    When _render_ordered_list is called
    Then it returns the Markdown heading and two numbered list items carrying "first" then "second"

  # hd: python/honest-render/honest-render.hd::_render_ordered_list
  Scenario: _render_ordered_list numbers route and entry rows without table syntax
    Given section: ViewSection is a routes section with two method, path and target rows or an entries section with two callsite and target rows
    When _render_ordered_list is called
    Then it returns the Markdown heading and one numbered list item per row in supplied order, preserving each row’s field order without inserting a table header or divider

  # hd: python/honest-render/honest-render.hd::_render_ordered_list
  Scenario: _render_ordered_list leaves only the heading for an empty section
    Given section: ViewSection is a routes section headed "Routes" with no rows
    When _render_ordered_list is called
    Then it returns only the Markdown section heading, with no list items

  Scenario: render_fault
    Given code: str and category: FaultCategory and message: str and detail: dict[str, str]
    When render_fault is called
    Then it builds one honest-render Fault record from its parts, the single place honest-render assembles a fault it originates
    And code is the specific reason: file_unreadable when read_source's ReadOutcome is not ok, or write_failed when write_document's WriteOutcome is not ok
    And category is the FaultCategory: client for file_unreadable (the caller named a path that could not be read) and server for write_failed (the destination honest-render was given could not be written)
    And message is the human sentence naming what went wrong and what to do instead
    And detail is the structured context: for file_unreadable the read error from the ReadOutcome's detail, for write_failed the write error from the WriteOutcome's detail
    And it sets the reserved is_err tag true and returns the Fault, carried by the return as a bare union arm and recognized by is_fault, never raised and never wrapped in an ok/err envelope
    And a passed-through honest-design read_hd fault is not built here; it keeps its own fields
    And it is pure: it reads no world
