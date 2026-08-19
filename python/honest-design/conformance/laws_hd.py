"""honest-design conformance: the generative proof (the behavioural circle).

Folds `.hd` source into the IR and pins every branch a data file cannot easily reach: both type-value
shapes (record and alias), union types and nested generics, set members with and without a
description, all four function roles and their derived columns, multiple side_effects across the
three directions, invokes, raises written bare and quoted, a route with and without a path, a module
with and without a layer, rules global and scoped, actors and flows, the malformed-source fault, the
Result constructors, reader determinism, and the public surface. Each probe returns a list of
failures; run() aggregates.
"""

from pathlib import Path

from honest_design import err, fault, ok, read_hd, render, validate
from honest_design import __all__ as PUBLIC


def _module(src):
    return read_hd(src)["ok"]["modules"][0]

_MODULE = """module m
  layer foundation
  type Rec = { a: str
 b: dict<str, set<str>> }
  type Alias = list<Ticket>
  set s = { "x" : "an x", "y" }
  vocabulary v = { s, s2 }
  dispatch d = { "k" -> h, "j" -> g }
  example e of c = "does a thing"
  boundary_in fn read_it : (r: Request) -> list<str> side_effect reads "HTTP"
  orchestrator fn run : (t: T) -> M invokes c, classify raises bad_input
  fn classify : (t: str) -> T | Fault
  boundary_out fn write_it : (t: T) -> Resp raises "io.failed" side_effect reads_writes "database" side_effect writes "network"
  chain c = classify -> write_it
  route "POST /orders" -> read_it
  entry "decorator:@h" -> run
  html_attr "hx-go" "navigate"
"""


def _probe_module():
    """A comprehensive module folds to the expected IR across every declaration kind."""
    bad = []
    result = read_hd(_MODULE)
    if "ok" not in result:
        return [f"comprehensive module did not read cleanly: {result}"]
    doc = result["ok"]
    if len(doc["modules"]) != 1 or doc["rules"] or doc["actors"] or doc["flows"]:
        bad.append(f"module file should yield exactly one module and no workspace decls: {doc.keys()}")
    m = doc["modules"][0]
    if m["name"] != "m" or m["layer"] != "foundation":
        bad.append(f"module name/layer wrong: {m['name']}/{m['layer']}")
    if [s["name"] for s in m["sets"]] != ["s"] or m["sets"][0]["members"] != [{"value": "x", "description": "an x"}, {"value": "y", "description": ""}]:
        bad.append(f"set members (with and without description) wrong: {m['sets']}")
    if m["vocabularies"] != [{"name": "v", "sets": ["s", "s2"]}]:
        bad.append(f"vocabulary wrong: {m['vocabularies']}")
    if m["dispatches"] != [{"name": "d", "entries": [{"key": "k", "handler": "h", "projection": ""}, {"key": "j", "handler": "g", "projection": ""}]}]:
        bad.append(f"dispatch wrong: {m['dispatches']}")
    if m["examples"] != [{"name": "e", "chain": "c", "text": "does a thing"}]:
        bad.append(f"example wrong: {m['examples']}")
    if m["chains"] != [{"name": "c", "links": ["classify", "write_it"]}]:
        bad.append(f"chain wrong: {m['chains']}")
    if m["routes"] != [{"method": "POST", "path": "/orders", "target": "read_it"}]:
        bad.append(f"route wrong: {m['routes']}")
    if m["entries"] != [{"callsite": "decorator:@h", "target": "run"}]:
        bad.append(f"entry wrong: {m['entries']}")
    if m["html_attrs"] != [{"attr": "hx-go", "description": "navigate"}]:
        bad.append(f"html_attr wrong: {m['html_attrs']}")
    return bad


def _probe_types():
    """Record fields, alias types, union types, and nested generics fold correctly."""
    bad = []
    m = read_hd(_MODULE)["ok"]["modules"][0]
    types = {t["name"]: t for t in m["types"]}
    rec = types["Rec"]
    if rec["alias"] or rec["record"] != [
        {"name": "a", "type": [{"name": "str", "args": []}]},
        {"name": "b", "type": [{"name": "dict", "args": [[{"name": "str", "args": []}], [{"name": "set", "args": [[{"name": "str", "args": []}]]}]]}]},
    ]:
        bad.append(f"record type / nested generic wrong: {rec}")
    alias = types["Alias"]
    if alias["record"] or alias["alias"] != [{"name": "list", "args": [[{"name": "Ticket", "args": []}]]}]:
        bad.append(f"alias type wrong: {alias}")
    return bad


def _probe_functions():
    """Every role maps to its column; side_effects, invokes, and raises (bare and quoted) fold."""
    bad = []
    fns = {f["name"]: f for f in read_hd(_MODULE)["ok"]["modules"][0]["functions"]}
    columns = {name: (fns[name]["role"], fns[name]["column"]) for name in fns}
    if columns != {
        "read_it": ("boundary_in", 1),
        "run": ("orchestrator", 2),
        "classify": ("fn", 3),
        "write_it": ("boundary_out", 4),
    }:
        bad.append(f"role -> column mapping wrong: {columns}")
    if fns["read_it"]["side_effects"] != [{"direction": "reads", "target": "HTTP"}]:
        bad.append(f"boundary_in side_effect wrong: {fns['read_it']['side_effects']}")
    if fns["write_it"]["side_effects"] != [{"direction": "reads_writes", "target": "database"}, {"direction": "writes", "target": "network"}]:
        bad.append(f"multiple side_effects / reads_writes wrong: {fns['write_it']['side_effects']}")
    if fns["run"]["invokes"] != ["c", "classify"] or fns["run"]["raises"] != ["bad_input"]:
        bad.append(f"invokes / bare raises wrong: {fns['run']}")
    if fns["write_it"]["raises"] != ["io.failed"]:
        bad.append(f"quoted raises should unquote: {fns['write_it']['raises']}")
    if fns["classify"]["ret"] != [{"name": "T", "args": []}, {"name": "Fault", "args": []}]:
        bad.append(f"union return type wrong: {fns['classify']['ret']}")
    if fns["read_it"]["params"] != [{"name": "r", "type": [{"name": "Request", "args": []}]}]:
        bad.append(f"params wrong: {fns['read_it']['params']}")
    return bad


def _probe_edges():
    """Branches the comprehensive module does not reach: a layerless module, a pathless route, a
    pure fn with no annotations, a global rule, and a scoped rule."""
    bad = []
    m = read_hd("module bare\n  route \"TICK\" -> f\n  fn pure_one : (x: str) -> str\n")["ok"]["modules"][0]
    if m["layer"] != "":
        bad.append(f"a module with no layer should have layer '': {m['layer']!r}")
    if m["routes"] != [{"method": "TICK", "path": "", "target": "f"}]:
        bad.append(f"a route with no path should have path '': {m['routes']}")
    pure = m["functions"][0]
    if pure["side_effects"] or pure["invokes"] or pure["raises"]:
        bad.append(f"a bare pure fn should have empty annotations: {pure}")
    return bad


def _probe_workspace():
    """Rules (global and scoped), actors, and flows fold; a workspace file yields no modules."""
    bad = []
    doc = read_hd(
        "rule HC001 = \"Every chain link references a declared function.\"\n"
        "rule HC-R001 on m = \"Every role is reachable.\"\n"
        "actor browser\nflow f in server = browser -> m -> other\n"
    )["ok"]
    if doc["modules"]:
        bad.append(f"a workspace file should yield no modules: {doc['modules']}")
    if doc["rules"] != [
        {"id": "HC001", "module": "", "statement": "Every chain link references a declared function."},
        {"id": "HC-R001", "module": "m", "statement": "Every role is reachable."},
    ]:
        bad.append(f"rules (global and scoped) wrong: {doc['rules']}")
    if doc["actors"] != [{"name": "browser"}]:
        bad.append(f"actor wrong: {doc['actors']}")
    if doc["flows"] != [{"name": "f", "group": "server", "steps": ["browser", "m", "other"]}]:
        bad.append(f"flow wrong: {doc['flows']}")
    return bad


def _probe_malformed():
    """Malformed source returns a client fault naming the exact location, never raises. Pinned in
    full so a blanked message or a swapped detail key is caught."""
    result = read_hd("module m\n  type T =\n")
    expected = {
        "err": {
            "code": "hd_syntax_error",
            "message": "Malformed .hd at line 2, column 11",
            "category": "client",
            "detail": {"line": 2, "col": 11},
        }
    }
    if result != expected:
        return [f"malformed fault wrong: {result}"]
    return []


def _probe_determinism():
    """The reader is pure: the same source folds to the same IR every time."""
    if read_hd(_MODULE) != read_hd(_MODULE):
        return ["read_hd is not deterministic on identical source"]
    return []


def _probe_result():
    """The Result constructors emit the shared shape verbatim."""
    bad = []
    if ok({"a": 1}) != {"ok": {"a": 1}}:
        bad.append("ok() wrong")
    f = fault("c", "m", "server", {"k": 1})
    if f != {"code": "c", "message": "m", "category": "server", "detail": {"k": 1}}:
        bad.append(f"fault() wrong: {f}")
    if err(f) != {"err": f}:
        bad.append("err() wrong")
    return bad


def _probe_surfaces():
    """A page's contract is which surfaces it renders and in what order, and until now the
    language could not say it. honest-page had no .hd at all because writing one required
    inventing syntax, and the missing file read as unfinished work rather than as a gap here.

    Square brackets carry the order: every other block in this grammar is unordered, so an
    ordered one gets a different bracket rather than a convention the reader must already know.
    The order is positional with no index, because a number beside each surface could disagree
    with the sequence, which is two copies of one fact."""
    bad = []
    page = (
        'module honest_page\n\n'
        '  surfaces PageSurfaces = [\n'
        '    "honest-alerts-banners" as div,\n'
        '    "honest-header" as header,\n'
        '    "honest-alerts-toasts" as div,\n'
        '    "honest-main" as main,\n'
        '    "honest-footer" as footer,\n'
        '    "honest-alerts-modal" as div\n'
        '  ]\n'
    )
    result = read_hd(page)
    if "ok" not in result:
        return [f"a surfaces block must parse: {result.get('err')}"]

    blocks = result["ok"]["modules"][0]["surfaces"]
    if len(blocks) != 1 or blocks[0]["name"] != "PageSurfaces":
        return [f"the block is named and there is one of it: {blocks}"]

    members = blocks[0]["members"]
    if [m["id"] for m in members] != [
        "honest-alerts-banners", "honest-header", "honest-alerts-toasts",
        "honest-main", "honest-footer", "honest-alerts-modal",
    ]:
        bad.append(f"the ids read back in the order they were declared: {[m['id'] for m in members]}")
    if [m["element"] for m in members] != ["div", "header", "div", "main", "footer", "div"]:
        bad.append(f"each member names the element it lives in: {[m['element'] for m in members]}")

    # Declaring none is a different fact from declaring nothing, so it must still parse and be
    # caught by the validator rather than by the grammar.
    empty = read_hd("module m\n\n  surfaces S = [\n  ]\n")
    if "ok" not in empty:
        bad.append("an empty block parses; refusing it is the validator's job, not the grammar's")

    # Every existing declaration must keep parsing: the block is new syntax, not a change to old.
    for hd in sorted(Path(__file__).resolve().parents[2].glob("honest-*/*.hd")):
        if "ok" not in read_hd(hd.read_text()):
            bad.append(f"{hd.name} stopped parsing")

    # The validator's two checks. Order is not among them: the declaration IS the order, so
    # there is nothing inside one module to compare it against.
    def _module(src):
        return read_hd(src)["ok"]["modules"][0]

    clean = validate(_module(page))
    if clean:
        bad.append(f"a well-formed surfaces block validates clean: {clean}")

    duped = validate(_module('module m\n\n  surfaces S = [\n    "a" as div,\n    "a" as main\n  ]\n'))
    if not duped or duped[0]["code"] != "duplicate_surface":
        bad.append(f"an id declared twice in one block is a fault: {duped}")
    elif "a" not in duped[0]["message"]:
        bad.append(f"the fault must name the id it caught: {duped[0]['message']}")
    elif duped[0]["detail"] != {"surfaces": "S", "id": "a"}:
        bad.append(f"the fault must locate itself by block and id: {duped[0]['detail']}")

    none = validate(_module("module m\n\n  surfaces S = [\n  ]\n"))
    if not none or none[0]["code"] != "empty_surfaces":
        bad.append(f"a block declaring no surface is a fault: {none}")
    return bad


def _probe_entry_boundaries():
    """read_hd and validate are the module's two public entry points, so they are boundaries and
    must answer a wrong input with a named fault rather than a traceback from somewhere inside.
    Both were found by the first consumer outside this workspace: bytes into read_hd raised
    AttributeError from source.encode, and the obvious composition validate(read_hd(src)) raised
    KeyError('functions') because one returns a document and the other takes a module."""
    bad = []

    byte_result = read_hd(b"module t\n")
    if "err" not in byte_result:
        bad.append("read_hd must refuse a non-text source rather than accept it")
    elif byte_result["err"]["code"] != "hd_source_not_text":
        bad.append(f"read_hd's refusal must name the code: {byte_result['err']['code']}")

    document = read_hd("module t\n")["ok"]
    faults = validate(document)
    if not faults or faults[0]["code"] != "not_a_module":
        bad.append(f"validate must name a document handed to it in place of a module: {faults}")
    elif "modules" not in faults[0]["message"]:
        bad.append("the refusal must say what to pass instead, naming the document's modules")
    if "err" in byte_result and "text" not in byte_result["err"]["message"]:
        bad.append("read_hd's refusal must say it wanted text")

    # A projection fault carries where it was found. Nothing asserted its detail, so the three
    # keys could be swapped for each other and every test still passed.
    projected = read_hd(
        "module m\n\n  type R = {\n    f: str\n  }\n\n"
        "  fn h : (f: str) -> str\n"
        "  fn c : (r: R) -> str invokes d\n"
        "  dispatch d = { \"k\" -> h from ghost }\n"
    )["ok"]["modules"][0]
    projection_faults = [f for f in validate(projected) if f["code"] == "unknown_projection"]
    if not projection_faults:
        bad.append("an unknown projection must fault")
    elif projection_faults[0]["detail"] != {"dispatch": "d", "key": "k", "projection": "ghost"}:
        bad.append(f"the fault must locate itself by dispatch, key and projection: {projection_faults[0]['detail']}")

    # Every fault the validator can emit, checked as one law rather than string by string: a
    # fault whose message or category is empty tells the reader nothing, and nothing here
    # asserted either, so any of them could have been blanked and every test still passed.
    mismatched = read_hd(
        "module m\n\n  type R = {\n    f: str\n  }\n\n"
        "  fn h : (n: int) -> str\n"
        "  fn c : (r: R) -> str invokes d\n"
        "  dispatch d = { \"k\" -> h from f }\n"
    )["ok"]["modules"][0]
    surface_faults = (
        validate(read_hd('module m\n\n  surfaces S = [\n    "a" as div,\n    "a" as main\n  ]\n')["ok"]["modules"][0])
        + validate(read_hd('module m\n\n  surfaces S = [\n  ]\n')["ok"]["modules"][0])
    )
    every = validate(projected) + validate(mismatched) + surface_faults + faults + [byte_result["err"]]
    for f in every:
        for field in ("code", "message", "category"):
            if not f[field]:
                bad.append(f"a fault carried an empty {field}: {f}")
    if {f["code"] for f in every} < {"unknown_projection", "projection_mismatch", "not_a_module", "hd_source_not_text", "duplicate_surface", "empty_surfaces"}:
        bad.append(f"the law must cover every code it claims: {sorted({f['code'] for f in every})}")
    return bad


def _probe_validate():
    """The validator raises nothing on a valid module and pins each fault it does raise."""
    bad = []
    if validate(_module(_MODULE)) != []:
        bad.append(f"the comprehensive (valid) module should validate clean: {validate(_module(_MODULE))}")
    unknown = validate(_module("module m\n  fn a : (x: str) -> str\n  chain c = a -> ghost\n"))
    if unknown != [{"code": "unknown_link", "message": "Chain 'c' references undeclared function 'ghost'", "category": "client", "detail": {"chain": "c", "link": "ghost"}}]:
        bad.append(f"unknown_link wrong: {unknown}")
    route = validate(_module("module m\n  fn a : (x: str) -> str\n  route \"GET /x\" -> ghost\n"))
    if route != [{"code": "unknown_target", "message": "Route 'GET /x' targets undeclared function 'ghost'", "category": "client", "detail": {"target": "ghost"}}]:
        bad.append(f"unknown_target (route) wrong: {route}")
    entry = validate(_module("module m\n  fn a : (x: str) -> str\n  entry \"deco\" -> ghost\n"))
    if entry != [{"code": "unknown_target", "message": "Entry 'deco' targets undeclared function 'ghost'", "category": "client", "detail": {"target": "ghost"}}]:
        bad.append(f"unknown_target (entry) wrong: {entry}")
    dup = validate(_module("module m\n  fn a : (x: str) -> str\n  fn a : (y: str) -> str\n"))
    if dup != [{"code": "duplicate_name", "message": "Duplicate function name 'a'", "category": "client", "detail": {"kind": "functions", "name": "a"}}]:
        bad.append(f"duplicate_name wrong: {dup}")
    impure = validate(_module("module m\n  fn a : (x: str) -> str side_effect reads \"X\"\n"))
    if impure != [{"code": "impure_pure_function", "message": "Pure function 'a' declares a side effect", "category": "server", "detail": {"function": "a"}}]:
        bad.append(f"impure_pure_function wrong: {impure}")
    return bad


def _probe_render():
    """The renderer places each function in its derived column, marks boundary effects, and draws
    each chain's adjacent links as edges."""
    diagram = render(_module(_MODULE))
    expected = {
        "module": "m",
        "columns": [
            {"index": 1, "title": "Input boundary", "nodes": [{"name": "read_it", "role": "boundary_in", "effects": ["HTTP"]}]},
            {"index": 2, "title": "Orchestrators", "nodes": [{"name": "run", "role": "orchestrator", "effects": []}]},
            {"index": 3, "title": "Pure functions", "nodes": [{"name": "classify", "role": "fn", "effects": []}]},
            {"index": 4, "title": "Output boundary", "nodes": [{"name": "write_it", "role": "boundary_out", "effects": ["database", "network"]}]},
        ],
        "edges": [{"chain": "c", "src": "classify", "dst": "write_it"}],
    }
    if diagram != expected:
        return [f"render wrong: {diagram}"]
    return []


def _probe_public_surface():
    if set(PUBLIC) != {"read_hd", "validate", "render", "ok", "err", "fault"}:
        return [f"public surface drifted: {PUBLIC}"]
    return []


def _probe_projection():
    """`from` reads back, stays optional, and is checked rather than decorative."""
    bad = []
    src = ("module m\n  type P = { a: str  b: int }\n  fn f : (a: str) -> bool\n"
           "  fn g : (b: int) -> bool\n  orchestrator fn r : (p: P) -> bool invokes D\n"
           "  dispatch D = { \"one\" -> f from a, \"two\" -> g from b }\n")
    entries = _module(src)["dispatches"][0]["entries"]
    if entries != [{"key": "one", "handler": "f", "projection": "a"}, {"key": "two", "handler": "g", "projection": "b"}]:
        bad.append(f"projection did not read back: {entries}")
    if validate(_module(src)) != []:
        bad.append(f"a matching projection should validate clean: {validate(_module(src))}")
    absent = _module("module m\n  fn f : (a: str) -> bool\n  dispatch D = { \"one\" -> f }\n")["dispatches"][0]["entries"]
    if absent != [{"key": "one", "handler": "f", "projection": ""}]:
        bad.append(f"an entry without `from` must still parse, projection empty: {absent}")
    ghost = validate(_module(src.replace("from a", "from zz")))
    if [f["code"] for f in ghost] != ["unknown_projection"]:
        bad.append(f"a projection naming no field must fault: {ghost}")
    mismatch = validate(_module(src.replace("fn g : (b: int)", "fn g : (b: str)")))
    if [f["code"] for f in mismatch] != ["projection_mismatch"]:
        bad.append(f"a handler that does not take the projected field must fault: {mismatch}")
    return bad


def run():
    probes = {
        "module": _probe_module(),
        "types": _probe_types(),
        "functions": _probe_functions(),
        "edges": _probe_edges(),
        "workspace": _probe_workspace(),
        "malformed": _probe_malformed(),
        "determinism": _probe_determinism(),
        "result": _probe_result(),
        "surfaces": _probe_surfaces(),
        "entry_boundaries": _probe_entry_boundaries(),
        "validate": _probe_validate(),
        "projection": _probe_projection(),
        "render": _probe_render(),
        "public_surface": _probe_public_surface(),
    }
    violations = [(name, messages) for name, messages in probes.items() if messages]
    for name, messages in violations:
        print(f"FAIL HD-probe [{name}]: {messages}")
    passed = sum(1 for messages in probes.values() if not messages)
    print(f"HD laws: {passed} passed, {len(violations)} failed, {len(probes)} total")
    return 0 if not violations else 1
