# honest-render: Architecture Specification

**Version:** 0.1 (Draft) **Date:** November 2026 **Status:** Draft **Author:** Adam Zachary Wasserman

---

## 1. Purpose and Scope

honest-render is a static renderer that makes a `.hd` architecture declaration human-readable. It takes one `.hd` file and produces a document a person reads the way they read a rendered Markdown preview: the module's purpose at the top, each function laid out with its role and signature and its note written as prose, and the types, sets and vocabularies set out as tables. It is a read-only view of a declaration, the same way a Markdown preview is a read-only view of a Markdown file.

honest-render is the public, free and open-source static renderer for `.hd`. It renders a declaration statically, from the declared data alone, with no interaction and no server.

The bug category honest-render addresses is the unread declaration. A `.hd` file is plain structured text, dense to read by eye, so an author or a reviewer who wants to understand a module's architecture tends to read the code instead of the declaration, and the declaration stops being consulted. honest-render makes the declaration the easier thing to read, so the artifact that is supposed to state the architecture is the artifact a person actually looks at.

### 1.1 What honest-render does

honest-render reads one `.hd` file and renders it as a human-readable document.

- It depends on honest-design and consumes two of honest-design's outputs, both through `import honest_design`: the `Module` intermediate representation from `read_hd` (honest-design section 4), and the `Diagram` from `render(module)` (honest-design section 7). It renders the document from those two values.
- It takes all column placement and all edges from honest-design's `Diagram`, and never recomputes the column rules. The rule that derives a function's column from its role lives in honest-design; honest-render consumes the result as data.
- It never parses `.hd` itself, and it never defines or owns any grammar. The grammar belongs to honest-parse and the read path belongs to honest-design. honest-render is a second consumer of honest-design's outputs, beside honest-design's own validator.
- It is deterministic: the same `.hd` file renders to byte-identical output every time (section 7).
- It renders Markdown first. HTML is a later output target built on the same view model (section 8).

### 1.2 What honest-render does not do (non-goals)

- **No editing.** honest-render never writes a `.hd` file and never lets anyone write one through it. It renders a declaration; it does not author one. This is the same boundary honest-design draws for its own renderer: the static half draws a given `.hd`, it does not draw into `.hd`.
- **No diagnostics.** honest-render reports no faults and no warnings about the declaration. Validation is honest-design's validator, and code-against-declaration conformance is honest-check. A live, in-editor diagnostics experience is honest-check with a language-server client, which is later work and a separate unit.
- **No editor shell.** This unit builds no VS Code extension and no other editor integration. A VS Code shell, and eventually the honest-check language-server client, come later and are out of scope here.
- **No re-parsing and no grammar.** Stated in 1.1 and repeated as a non-goal because it is the hard dependency rule: if honest-render ever needed to parse, the design would be wrong. It consumes honest-design's `read_hd` and `render` outputs only.
- **No recomputing honest-design's layout.** honest-render never re-derives a function's column or the diagram edges. Column placement and edges are honest-design's projection, consumed from the `Diagram` as data.

### 1.3 Position in the build order and dependency

honest-render builds after honest-design, because it consumes honest-design's reader output:

```
parse                     the shared tree-sitter boundary
design    -> parse        the .hd layer: grammar, reader, validator, static diagram renderer
render    -> design       the human-readable static renderer of a .hd file
```

honest-design is honest-render's only framework dependency. honest-render reaches honest-parse only transitively, through honest-design's `read_hd`, and never directly, because it never parses.

The dependency runs one way: `render -> design`, a higher layer importing a lower one. honest-render imports honest-design; honest-design never imports honest-render and never learns about it. The document view is honest-render's and stays in honest-render: the readable-document projection never moves into honest-design, which keeps producing only the `Module` and the `Diagram`.

honest-design needs one added line to be reached this way: an `entry "import honest_design" -> render` on honest-design's `render`, so the diagram producer has a named import entry its consumer reaches. Adam approved this as the only change to honest-design. `Diagram`, `DiagramNode`, `Column`, and `Edge` are already data types honest-design publishes (honest-design section 7), so nothing else in honest-design changes.

### 1.4 Reference implementation

The reference implementation is `python/honest-render/`. honest-render is a separate package from honest-design; it is not a subpackage and it does not reach into honest-design's internals. It depends on honest-design's published read path (`read_hd` and the `Module` intermediate representation) and on nothing else of honest-design's. When this document and the implementation disagree, this document is correct.

---

## 2. Inputs and Outputs

**Input:** a path to one `.hd` file.

**Output:** a human-readable rendering of that file. Markdown is the first and normative output format. HTML is a later target produced from the same view model (section 8).

honest-render's world is small and declared. It reads one file from the filesystem and writes one document. The output destination is one field, `path: str` or `NOTHING`: a path writes the document to that file, and `NOTHING` writes it to standard output. There is no boolean flag; the single field, present or absent, is the whole choice. The input filename and the output path are learned at run time, from the command line or the caller, so the file sides are named `given` in the sense honest-design's side-kind rules use (honest-design section 6): the module is handed its path, it does not fix one at declaration.

---

## 3. The rendering pipeline

honest-render is one pipeline with four kinds of function, placed the way honest-design's model places them: boundaries at the edges, an orchestrator above the pure core, and the pure core in the middle. The shape is a door, a reader, a pure core of two steps, and an output boundary.

### 3.1 The door

A single input boundary accepts the request to render. It takes the `.hd` path (and the chosen output target), checks its own input because a boundary cannot assume the caller's types, and hands the request to exactly one orchestrator. The door is the one entry the command line or a caller reaches; honest-render lists it on an entry so the world has a named way in.

The Python package `honest_render` lists only `render_file` in its literal `__all__`. Other existing package bindings remain available through explicit named imports.

### 3.2 The reader

A reader reads the `.hd` file text from the filesystem at the boundary. Reading the file is honest-render's only input side effect. The reader stays thin and builds no `Fault`: it returns a read outcome record (`ok: bool`, `text: str`, `detail: str`), the boundary's plain report of what the filesystem did. `ok` is true with the file text in `text` on a clean read, and false with the read error in `detail` on a failure. The orchestrator reads this outcome and builds the `Fault`; the reader does not parse the text and does not interpret it. This follows honest-observe's `append_event` outcome pattern (honest-observe section 3), where the write boundary reports a plain outcome and the orchestrator builds the fault.

### 3.3 The pure core

The orchestrator composes the work above the pure core. It takes the file text from the reader, then obtains two values from honest-design, both through `import honest_design`: the `Module` intermediate representation from `read_hd(text)`, and the `Diagram` from `render(module)`. honest-render performs no parse and no column computation; it imports the producer of each value and consumes the result. The orchestrator then drives two pure steps:

1. **Build the document view.** A pure function takes the `Module` and the `Diagram` and produces a `ViewModel` (section 4): the declaration reorganized into the order and groupings a reader wants. Column placement and edges come from the `Diagram`; the per-declaration detail (notes, signatures, invokes, the type, set and vocabulary tables, the entries) comes from the `Module`. This step decides structure, not text.
2. **Render the document view.** A pure function takes the `ViewModel` and produces the output document as a string: Markdown first. This step decides text, not structure.

Splitting structure from text is deliberate. The view model is the one place honest-render's document-view rules (section 5) are applied, and it is the shared input to every output format, so Markdown and the later HTML render the same structure and cannot drift into showing different things.

The orchestrator owns fault construction, because the boundaries stay thin (sections 3.2 and 3.4). It reads the reader's read outcome and, when the read failed, builds a `file_unreadable` `Fault` itself; it reads the output boundary's write outcome and, when the write failed, builds a `write_failed` `Fault` itself. This is honest-observe's `append_event` pattern: the boundary reports a plain outcome, the orchestrator builds the fault.

honest-render's `Fault` carries a bounded `category`, a declared closed set of `client` or `server`, the two values honest-type defines in its Fault schema (honest-type section 13.2). `file_unreadable` is `client` (the caller named a path that could not be read), and `write_failed` is `server` (the destination the module was given could not be written). If `read_hd` returns a fault (the `.hd` is malformed or is not a valid declaration), that fault passes through with its own meaning and its own category; honest-render surfaces it as data rather than rendering a partial or invented document. honest-render adds no diagnostics of its own (section 1.2); it reports honest-design's fault faithfully and renders nothing.

### 3.4 The output boundary

An output boundary writes the rendered document to its destination, which is one field, `path: str` or `NOTHING`: a `path` writes the document to that file, and `NOTHING` writes it to standard output. There is no boolean flag; the field's presence or absence is the whole choice. Writing is honest-render's only output side effect. The pure core produced the bytes; the boundary only puts them where they go. The boundary stays thin and builds no `Fault`: it returns a write outcome record (`ok: bool`, `detail: str`), `ok` true on a clean write and false with the write error in `detail` on a failure, and the orchestrator reads that outcome and builds the `Fault`, again following honest-observe's `append_event` outcome pattern (honest-observe section 3).

---

## 3b. Fault codes

honest-render renders exactly one module per `.hd`. When `read_hd` returns a Document carrying zero modules or more than one, honest-render renders nothing and returns a client Fault with code `not_single_module`, whose `detail` states the module count found.

honest-render's own Faults are built by `render_fault` and carry a `code`, a bounded `category` (`client` or `server`, honest-type section 13.2), a `message`, and a `detail`. honest-render originates exactly three codes; a fault from honest-design's `read_hd` is passed through with its own code and category, never re-coded.

| Code | Category | Raised when |
|---|---|---|
| `file_unreadable` | client | The reader's read outcome is not ok: the `.hd` path could not be read. The caller named a path that does not read. |
| `write_failed` | server | The output boundary's write outcome is not ok: the destination could not be written. |
| `not_single_module` | client | `read_hd` returned a Document carrying zero modules or more than one, so there is not exactly one module to render. The `detail` states the module count found. |
| (passed through) | (its own) | `read_hd` reported the `.hd` is malformed or not a valid declaration. honest-render surfaces honest-design's Fault unchanged, keeping its own `code`, `message`, and `category`, and renders nothing. It does not re-wrap or re-code it. |

The structured detail for `file_unreadable` carries `read_error` with the reader's reported reason. For `write_failed`, `write_error` carries the writer's reported reason. For `not_single_module`, `module_count` carries the decimal string for the number of modules found. The `not_single_module` message states the condition and the next action: for zero modules, explain that the declaration contains no modules and ask the caller to supply one; for more than one, explain that the declaration contains multiple modules and direct the caller to render them individually.

A `client` code marks input the caller can correct; a `server` code marks a fault the caller cannot. honest-render returns every one as data, by return, never raised.

## 4. The view model

The view model is plain data, derived purely from honest-design's `Module` intermediate representation and honest-design's `Diagram`. It is the rendering-shaped projection of the declaration: the facts those two values hold, reorganized into the sections and tables a reader reads, and carrying only what the renderer needs. Column placement and edges are taken from the `Diagram`; everything else is taken from the `Module`.

The view model holds, in rendering order:

- The module heading: name, layer, version, and the module note as the opening prose.
- The world: the declared inputs and outputs, and the sides the boundaries touch, each shown with the family path honest-design assigns its kind so a reader sees the whole address of a side rather than the bare kind word.
- The functions, grouped and placed by the `Diagram`'s columns, each carrying its signature, its invokes, the sides it touches, and its note from the `Module`.
- The types, sets, vocabularies, and dispatches, each as a table.
- The chains, the routes, and the entries, each as an ordered list.
- The exposes, the surfaces, and the examples, where the declaration carries them.

The view model names no colors, no widths, and no output syntax. It is the structure; the renderer of each output format turns it into text.

---

## 5. The document-view rules

The layout is honest-design's projection, not honest-render's. honest-design's `render` already decides which column each function sits in and which edges join the chains, and returns that as the `Diagram` (honest-design section 7). honest-render consumes that `Diagram` as data: it places functions in the columns the `Diagram` gives, draws the edges the `Diagram` gives, and never recomputes a column rule or an edge. If honest-design changes how it places functions, honest-render follows automatically, because it reads the result rather than a copy of the rule.

What follows are the rules that are honest-render's own: how the readable document presents the per-declaration detail the `Module` carries. They add nothing the declaration does not state.

**One function, shown whole.** Each function is shown with its role, its full signature (its parameters with their types and its return type, unions included), the functions it invokes, the sides of the world it reads or writes, and whether it is awaited. Its note is rendered as prose, as the sentence the author wrote while they held the context, not as a code comment. The note is the human explanation, so it is given the position of prose in the document.

**Data as tables.** Types, sets, vocabularies, and dispatches are rendered as tables. A type shows its fields and their types. A set and a vocabulary show their members. A dispatch shows each key and the function it selects. A table is the readable form of a closed, enumerable structure, so the closed structures of the declaration are rendered as tables.

**Lists in declared order.** Chains, routes, and entries are rendered as ordered lists. A chain lists its links in order, because the order is the pipeline. Routes list method, path, and target. Entries list the external callsite string and the function it names. Where the declaration fixes an order, the rendering preserves it, because in `.hd` the declared order is part of the contract.

**Nothing invented.** The rendering shows what the declaration states and marks what the declaration omits as omitted. It never fills a missing note with a guess and never derives a fact the declaration does not carry. If the `Module` and the `Diagram` do not hold it, the document does not show it.

---

## 6. Relationship to other modules

- **honest-design** is honest-render's one dependency, imported one way (`render -> design`). honest-render consumes two of honest-design's outputs through `import honest_design`: the `Module` from `read_hd` (honest-design section 4) and the `Diagram` from `render(module)` (honest-design section 7). honest-design's `render` already decides column placement and chain edges and returns them in the `Diagram`; honest-render consumes that layout as data and adds the readable-document presentation on top. The document view is honest-render's and stays in honest-render; honest-design keeps producing only the `Module` and the `Diagram` and never learns about the document view. The one change honest-design needs is a single `entry "import honest_design" -> render` so the diagram producer is reachable by import; Adam approved that as the only honest-design change, and the `Diagram`, `DiagramNode`, `Column`, and `Edge` types it already publishes need no change.
- **honest-parse** is reached only transitively, through honest-design's read path. honest-render never calls honest-parse and never touches a grammar.
- **honest-check** is not a dependency and not a consumer. Code-against-declaration checking and in-editor diagnostics are honest-check's, including the later language-server client. honest-render renders; it does not check.

---

## 7. Determinism

honest-render is deterministic. The same `.hd` file, rendered to the same output format, produces byte-identical output every time. There is no interaction, no layout randomness, no clock in the output, and no external state read into the document. The rendering is a pure function of the declaration, so two runs over the same file agree to the byte, and a rendering can be regenerated and compared as a fixed artifact.

Determinism is why the pipeline splits the view model from the text (section 3.3): the view model is a pure function of the intermediate representation, and the output text is a pure function of the view model, so the whole rendering is a composition of pure functions over the file text, with I/O only at the reader and the output boundary.

---

## 8. Output formats

Markdown is the first output format and the normative one. It renders the document described in sections 4 and 5: the module heading and note as prose, functions as prose with their signatures, data as Markdown tables, chains and routes and entries as Markdown lists.

HTML is a later target. It is produced from the same view model (section 4), so it shows the same structure as the Markdown rendering and cannot drift from it. Adding HTML is adding a second renderer of the view model, never a second way of reading the `.hd` file.

The output formats are the only place output syntax lives. The view model and the projection rules are format-independent, so a new output format reads the view model and does not re-derive the structure.

---

## 9. Conformance

A conforming honest-render:

- Depends on honest-design and renders only from its `read_hd` and `render` outputs, both reached through `import honest_design`. It does not parse `.hd`, declares no grammar, and never recomputes column placement or edges (those come from the `Diagram`).
- Renders Markdown as its first output format, from the view model.
- Is deterministic: the same `.hd` file renders byte-identically on repeated runs.
- Surfaces a honest-design fault as data when `read_hd` reports the `.hd` is malformed or invalid, and renders no document in that case.
- Adds no diagnostics, performs no editing, and ships no editor shell.

A conformance suite renders a fixed corpus of `.hd` files and compares each rendering against a stored expected output, so a change that alters the rendering is caught as a byte difference against the fixtures.

---

## 10. Non-goals, restated

honest-render is the static, read-only renderer of one `.hd` file. It does not edit, it does not diagnose, it does not parse, it owns no grammar, and it ships no editor shell. Everything beyond rendering a declaration to a readable document is another module's or a later unit's work: validation is honest-design, conformance and in-editor diagnostics are honest-check, and the editor shell and the language-server client are later.
