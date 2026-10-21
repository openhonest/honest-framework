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

from honest_design import err, fault, ok, read_hd, reach, render, validate
from honest_design import __all__ as PUBLIC


def _module(src):
    return read_hd(src)["ok"]["modules"][0]

_MODULE = """module m
  layer foundation
  inputs = { "HTTP", "database" }
  outputs = { "database", "network" }
  env DATABASE_URL : str
  env POOL_SIZE : int | Absent
  type Rec = { a: str
 b: dict<str, set<str>> }
  type Alias = list<Ticket>
  set s = { "x" : "an x", "y" }
  vocabulary v = { s, s2 }
  dispatch d = { "k" -> h, "j" -> g }
  example e of c = "does a thing"
  boundary_in fn read_it : (r: Request) -> list<str> side_effect reads "HTTP"
  orchestrator fn run : (t: T) -> M | Fault invokes c, classify raises bad_input
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
    if m["vocabularies"] != [{"name": "v", "sets": ["s", "s2"], "note": ""}]:
        bad.append(f"vocabulary wrong: {m['vocabularies']}")
    if m["dispatches"] != [{"name": "d", "entries": [{"key": "k", "handler": "h", "projection": ""}, {"key": "j", "handler": "g", "projection": ""}], "note": ""}]:
        bad.append(f"dispatch wrong: {m['dispatches']}")
    if m["examples"] != [{"name": "e", "chain": "c", "text": "does a thing"}]:
        bad.append(f"example wrong: {m['examples']}")
    if m["chains"] != [{"name": "c", "links": ["classify", "write_it"], "note": ""}]:
        bad.append(f"chain wrong: {m['chains']}")
    if m["routes"] != [{"method": "POST", "path": "/orders", "target": "read_it", "label": ""}]:
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

    # A foreign type names its source and declares no fields, because describing someone else's
    # object is a copy that drifts. tree-sitter's node is the case it exists for.
    foreign = read_hd('module m\n  type Node = foreign "tree-sitter"\n  fn f : (n: Node) -> str\n')
    assert "ok" in foreign, foreign
    node = {t["name"]: t for t in foreign["ok"]["modules"][0]["types"]}["Node"]
    if node["foreign"] != "tree-sitter" or node["record"] or node["alias"]:
        bad.append(f"a foreign type carries its source and no fields: {node}")
    if validate(foreign["ok"]["modules"][0]):
        bad.append(f"a function naming a foreign type validates clean: {validate(foreign['ok']['modules'][0])}")

    # A record and an alias carry no foreign source, so the field tells the three apart.
    if rec["foreign"] or alias["foreign"]:
        bad.append(f"a record and an alias name no foreign source: rec={rec['foreign']!r} alias={alias['foreign']!r}")
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
    if fns["read_it"]["side_effects"] != [{"direction": "reads", "target": "HTTP", "module": "", "door": ""}]:
        bad.append(f"boundary_in side_effect wrong: {fns['read_it']['side_effects']}")
    if fns["write_it"]["side_effects"] != [{"direction": "reads_writes", "target": "database", "module": "", "door": ""}, {"direction": "writes", "target": "network", "module": "", "door": ""}]:
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
    if m["routes"] != [{"method": "TICK", "path": "", "target": "f", "label": ""}]:
        bad.append(f"a route with no path should have path '': {m['routes']}")
    labelled = read_hd('module labelled\n  route "GET /channels" as "Channel list" -> h\n  fn h : (r: str) -> str\n')["ok"]["modules"][0]
    if labelled["routes"] != [{"method": "GET", "path": "/channels", "target": "h", "label": "Channel list"}]:
        bad.append(f"a route with an as-label should carry it: {labelled['routes']}")
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


def _probe_envs():
    """Environment variables fold to (name, type), a declared read is clean, an undeclared read is a fault."""
    bad = []
    m = _module(_MODULE)
    clean = validate(_module("module m\n  inputs = { }\n  env A : str\n  boundary_in fn c : () -> str side_effect reads \"env:A\"\n"))
    if clean != []:
        bad.append(f"a declared env read should validate clean: {clean}")
    if m["envs"] != [{"name": "DATABASE_URL", "type": [{"name": "str", "args": []}], "note": ""},
                     {"name": "POOL_SIZE", "type": [{"name": "int", "args": []}, {"name": "Absent", "args": []}], "note": ""}]:
        bad.append(f"envs wrong: {m['envs']}")
    ghost = validate(_module("module m\n  inputs = { }\n  env A : str\n  boundary_in fn c : () -> str side_effect reads \"env:A\" side_effect reads \"env:GHOST\"\n"))
    if ghost != [{"code": "unknown_env", "message": "Function 'c' reads environment variable 'GHOST', which no env declares", "category": "client", "detail": {"function": "c", "env": "GHOST"}}]:
        bad.append(f"unknown_env wrong: {ghost}")
    cycle = validate(_module("module m\n  type A = B\n  type B = A\n  type C = str\n  fn f : (a: A, c: C) -> str\n"))
    if cycle != []:
        bad.append(f"an alias cycle leads to no handle and must not fault or hang: {cycle}")
    dup = validate(_module("module m\n  env A : str\n  env A : int\n"))
    if dup != [{"code": "duplicate_name", "message": "Duplicate env name 'A'", "category": "client", "detail": {"kind": "envs", "name": "A"}}]:
        bad.append(f"duplicate env wrong: {dup}")
    return bad


def _probe_handles():
    """A handle is held and passed, never read: the scalar and its aliases, through records and generics."""
    bad = []
    src = ("module m\n  outputs = { \"network\" }\n  type Connection = handle\n  type Conn2 = Connection\n  type Database = { conn: Connection }\n"
           "  boundary_out fn open_it : (target: str) -> Connection side_effect writes \"network\"\n"
           "  boundary_out fn close_it : (c: Conn2) -> bool side_effect writes \"network\"\n"
           "  fn carry : (db: Database) -> Database\n"
           "  fn peek : (c: Connection) -> str\n"
           "  fn peek_all : (cs: list<Conn2>) -> handle\n")
    got = validate(_module(src))
    want = [
        {"code": "handle_read", "message": "Pure function 'peek' names the handle 'Connection' in its signature; a handle is held and passed to a boundary, never read", "category": "server", "detail": {"function": "peek", "handle": "Connection"}},
        {"code": "handle_read", "message": "Pure function 'peek_all' names the handle 'Conn2' in its signature; a handle is held and passed to a boundary, never read", "category": "server", "detail": {"function": "peek_all", "handle": "Conn2"}},
        {"code": "handle_read", "message": "Pure function 'peek_all' names the handle 'handle' in its signature; a handle is held and passed to a boundary, never read", "category": "server", "detail": {"function": "peek_all", "handle": "handle"}},
    ]
    if got != want:
        bad.append(f"handle_read wrong: {got}")
    return bad


def _probe_faults():
    """A fault bubbles up through returns, along invokes, dispatch tables and chains; and Fault has a shape."""
    bad = []
    src = ("module m\n  inputs = { \"HTTP\" }\n  outputs = { \"stdout\" }\n  type Fault = { what_went_wrong: str\n what_to_do_instead: str }\n"
           "  dispatch by_kind = { \"a\" -> fine, \"b\" -> fails }\n"
           "  boundary_in fn door : (r: str) -> str side_effect reads \"HTTP\"\n"
           "  orchestrator fn run : (r: str) -> str invokes by_kind\n"
           "  orchestrator fn run_ok : (r: str) -> str | Fault invokes fails\n"
           "  fn fine : (r: str) -> str\n"
           "  fn fails : (r: str) -> str | Fault\n"
           "  boundary_out fn sink : (s: str) -> bool | Fault side_effect writes \"stdout\"\n"
           "  chain c = door -> run_ok -> sink\n")
    got = validate(_module(src))
    want = [{"code": "fault_swallowed", "message": "Function 'run' calls 'fails', which can fault, and cannot return one", "category": "server", "detail": {"function": "run", "callee": "fails"}},
            {"code": "fault_swallowed", "message": "Function 'door' calls 'run_ok', which can fault, and cannot return one", "category": "server", "detail": {"function": "door", "callee": "run_ok"}}]
    if got != want:
        bad.append(f"fault_swallowed wrong: {got}")
    # A boundary discharges the last fault by raising it. The chain carries faults as data and the
    # boundary is the one place an exception is permitted (framework spec: faults as data through
    # chains, exceptions only at the boundary). Some failures cannot be carried by a return at all,
    # because a caller is free to ignore one: a door that must stop a server starting has to raise,
    # and a server that boots on an ignored return serves requests against nothing.
    raising = ("module m\n  inputs = { \"HTTP\" }\n  type Fault = { what_went_wrong: str\n what_to_do_instead: str }\n"
               "  boundary_in fn door : (r: str) -> str raises could_not_open side_effect reads \"HTTP\"\n"
               "  orchestrator fn run : (r: str) -> str | Fault invokes fails\n"
               "  fn fails : (r: str) -> str | Fault\n"
               "  chain c = door -> run\n")
    if [f for f in validate(_module(raising)) if f["code"] == "fault_swallowed"]:
        bad.append(f"a door that declares what it raises has answered for its callee's fault: {validate(_module(raising))}")

    # A pure function or an orchestrator is inside the chain, so no raises clause excuses it.
    inside = ("module m\n  type Fault = { what_went_wrong: str\n what_to_do_instead: str }\n"
              "  orchestrator fn run : (r: str) -> str raises could_not_open invokes fails\n"
              "  fn fails : (r: str) -> str | Fault\n")
    if not [f for f in validate(_module(inside)) if f["code"] == "fault_swallowed"]:
        bad.append("an orchestrator inside the chain returns the fault or swallows it; raises does not excuse it")

    shape_fault = {"code": "fault_shape", "message": "Fault is declared without the fields to say what went wrong and what to do instead", "category": "server", "detail": {"type": "Fault"}}
    thin = validate(_module("module m\n  type Fault = str\n  fn f : (a: str) -> str | Fault\n"))
    if thin != [shape_fault]:
        bad.append(f"fault_shape (alias) wrong: {thin}")
    one = validate(_module("module m\n  type Fault = { what_went_wrong: str }\n  fn f : (a: str) -> str | Fault\n"))
    if one != [shape_fault]:
        bad.append(f"fault_shape (one field) wrong: {one}")
    unused = validate(_module("module m\n  type Fault = str\n  fn f : (a: str) -> str\n"))
    if unused != []:
        bad.append(f"a thin Fault nobody returns is not checked: {unused}")
    elsewhere = validate(_module("module m\n  fn f : (a: str) -> str | Fault\n"))
    if elsewhere != []:
        bad.append(f"a Fault declared elsewhere should not fault the shape: {elsewhere}")
    return bad


def _probe_readers():
    """A door is called by the world only; a reader is called by the program and calls nothing."""
    bad = []
    src = ("module m\n  inputs = { \"HTTP\", \"clock\", \"filesystem\" }\n  outputs = { \"stdout\" }\n"
           "  boundary_in fn door : (r: str) -> str side_effect reads \"HTTP\"\n"
           "  boundary_in fn side_door : (r: str) -> str side_effect reads \"HTTP\"\n"
           "  reader fn read_clock : () -> float side_effect reads \"clock\"\n"
           "  reader fn read_dir : (p: str) -> list<str> side_effect reads \"filesystem\" invokes shape\n"
           "  orchestrator fn run : (r: str) -> str invokes read_clock, side_door, shape\n"
           "  fn shape : (r: str) -> str\n"
           "  boundary_out fn sink : (s: str) -> bool side_effect writes \"stdout\"\n"
           "  chain c = door -> run -> sink\n"
           "  chain d = read_clock -> run\n")
    m = _module(src)
    if m["functions"][2]["column"] != 1:
        bad.append(f"a reader stands in column 1: {m['functions'][2]}")
    got = validate(m)
    want = [{"code": "door_called", "message": "Function 'run' calls 'side_door', a door; the world calls a door, nothing inside does. A read the program asks for is a reader", "category": "server", "detail": {"function": "run", "callee": "side_door"}},
            {"code": "reader_calls", "message": "Reader 'read_dir' calls 'shape'; a reader answers the program and asks nothing of it", "category": "server", "detail": {"function": "read_dir", "callee": "shape"}},
            {"code": "reader_calls", "message": "Reader 'read_clock' calls 'run'; a reader answers the program and asks nothing of it", "category": "server", "detail": {"function": "read_clock", "callee": "run"}}]
    if got != want:
        bad.append(f"door/reader faults wrong: {got}")
    return bad


def _probe_stores():
    """A store holds one pure function's answers, is named by the orchestrator that keeps them, and by nothing else."""
    bad = []
    src = ("module m\n  inputs = { \"HTTP\" }\n  outputs = { \"stdout\" }\n"
           "  store compiled = compile_it \"a statement is built once; render.feature\"\n"
           "  store wrong = door \"held from the world\"\n"
           "  boundary_in fn door : (r: str) -> str side_effect reads \"HTTP\" side_effect reads_writes \"store:compiled\"\n"
           "  orchestrator fn run : (r: str) -> str invokes compile_it side_effect reads_writes \"store:compiled\" side_effect reads \"store:GHOST\"\n"
           "  fn compile_it : (r: str) -> str\n"
           "  boundary_out fn sink : (s: str) -> bool side_effect writes \"stdout\"\n"
           "  chain c = door -> run -> sink\n")
    m = _module(src)
    if m["stores"] != [{"name": "compiled", "fn": "compile_it", "why": "a statement is built once; render.feature"},
                       {"name": "wrong", "fn": "door", "why": "held from the world"}]:
        bad.append(f"stores wrong: {m['stores']}")
    got = [f for f in validate(m) if "store" in f["code"]]
    want = [{"code": "store_of_impure", "message": "Store 'wrong' holds the answers of 'door', which is not a pure fn; only a pure function's answer can be held without going stale", "category": "server", "detail": {"store": "wrong", "fn": "door"}},
            {"code": "unknown_store", "message": "Function 'run' reaches store 'GHOST', which no store declares", "category": "client", "detail": {"function": "run", "store": "GHOST"}},
            {"code": "store_not_orchestrator", "message": "Function 'door' reaches store 'compiled', and it is a boundary_in; only an orchestrator keeps what a step returned", "category": "server", "detail": {"function": "door", "store": "compiled"}}]
    if got != want:
        bad.append(f"store faults wrong: {got}")
    clean = validate(_module("module m\n  store s = f \"why\"\n  orchestrator fn run : (r: str) -> str invokes f side_effect reads_writes \"store:s\"\n  fn f : (r: str) -> str\n"))
    if clean != []:
        bad.append(f"a well-formed store should validate clean: {clean}")
    pure = validate(_module("module m\n  store s = f \"why\"\n  fn f : (r: str) -> str side_effect reads_writes \"store:s\"\n"))
    if pure != [{"code": "impure_pure_function", "message": "Pure function 'f' declares a side effect", "category": "server", "detail": {"function": "f"}}]:
        bad.append(f"a pure fn reaching a store is impure and nothing else: {pure}")
    out = validate(_module("module m\n  store s = f \"why\"\n  fn f : (r: str) -> str\n  boundary_out fn sink : (s: str) -> bool side_effect writes \"stdout\" side_effect reads_writes \"store:s\"\n"))
    if [(x["code"], x["detail"]["function"]) for x in out if x["code"] == "store_not_orchestrator"] != [("store_not_orchestrator", "sink")]:
        bad.append(f"an output boundary reaching a store: {out}")
    dup = validate(_module("module m\n  store s = f \"a\"\n  store s = f \"b\"\n  fn f : (r: str) -> str\n"))
    if dup != [{"code": "duplicate_name", "message": "Duplicate store name 's'", "category": "client", "detail": {"kind": "stores", "name": "s"}}]:
        bad.append(f"duplicate store wrong: {dup}")
    return bad


def _probe_notes():
    """A note rides on the declaration it explains and is "" when absent, on every kind that takes one."""
    bad = []
    src = ("module m\n  env A : str note \"the account\"\n  type T = { a: str } note \"a record\"\n  type U = list<str>\n"
           "  set s = { \"x\" } note \"a set\"\n  vocabulary v = { s } note \"a vocabulary\"\n"
           "  dispatch d = { \"x\" -> f } note \"a table\"\n"
           "  orchestrator fn run : (t: T) -> str note \"runs\" invokes d note \"the sequence\" raises bad_input\n  fn f : (t: T) -> str\n"
           "  chain c = run -> f note \"a chain\"\n")
    m = _module(src)
    got = {"env": m["envs"][0]["note"], "type": m["types"][0]["note"], "alias": m["types"][1]["note"],
           "set": m["sets"][0]["note"], "vocab": m["vocabularies"][0]["note"], "dispatch": m["dispatches"][0]["note"],
           "fn": m["functions"][0]["note"], "plain": m["functions"][1]["note"], "chain": m["chains"][0]["note"]}
    want = {"env": "the account", "type": "a record", "alias": "", "set": "a set", "vocab": "a vocabulary",
            "dispatch": "a table", "fn": "runs the sequence", "plain": "", "chain": "a chain"}
    if got != want:
        bad.append(f"notes wrong: {got}")
    if m["functions"][0]["invokes"] != ["d"] or m["functions"][0]["raises"] != ["bad_input"]:
        bad.append("a note among the annotations disturbed its neighbours")
    return bad


def _probe_surface():
    """The surface is closed: every side a boundary touches is listed, every listed side is touched, and a door takes nothing a reader returns."""
    bad = []
    src = ("module m\n"
           "  inputs = { \"caller\" : \"a library call\", \"clock\", \"idle\" }\n"
           "  outputs = { \"database\", \"stdout\" }\n"
           "  env A : str\n  store s = shape \"kept\"\n"
           "  type Models = list<str>\n"
           "  boundary_in fn door : (r: str, models: Models) -> str side_effect reads \"caller\" side_effect reads \"env:A\"\n"
           "  boundary_in fn mute : (r: str) -> str\n"
           "  reader fn read_models : () -> Models side_effect reads \"filesystem\"\n"
           "  reader fn read_clock : () -> float side_effect reads \"clock\"\n"
           "  orchestrator fn run : (r: str) -> str invokes shape, read_clock, read_models, sink, peek side_effect reads_writes \"store:s\"\n"
           "  fn shape : (r: str) -> str\n"
           "  boundary_out fn sink : (s: str) -> bool side_effect reads_writes \"database\"\n"
           "  boundary_out fn peek : (s: str) -> bool side_effect reads \"stdout\"\n"
           "  boundary_out fn spill : (s: str) -> bool side_effect writes \"network\"\n"
           "  boundary_in fn back : (r: str) -> str side_effect writes \"database\"\n"
           "  chain c = door -> run -> sink\n")
    m = _module(src)
    if m["inputs"] != [{"value": "caller", "description": "a library call"}, {"value": "clock", "description": ""}, {"value": "idle", "description": ""}] or m["outputs"] != [{"value": "database", "description": ""}, {"value": "stdout", "description": ""}]:
        bad.append(f"surface lists wrong: {m['inputs']} {m['outputs']}")
    got = [f for f in validate(m) if f["code"].startswith(("surface", "boundary_without", "door_takes"))]
    want = [{"code": "surface_unknown", "message": "Function 'read_models' reads 'filesystem', which inputs does not list", "category": "client", "detail": {"function": "read_models", "target": "filesystem", "side": "inputs"}},
            {"code": "surface_unknown", "message": "Function 'sink' reads 'database', which inputs does not list", "category": "client", "detail": {"function": "sink", "target": "database", "side": "inputs"}},
            {"code": "surface_unknown", "message": "Function 'peek' reads 'stdout', which inputs does not list", "category": "client", "detail": {"function": "peek", "target": "stdout", "side": "inputs"}},
            {"code": "surface_unknown", "message": "Function 'spill' writes 'network', which outputs does not list", "category": "client", "detail": {"function": "spill", "target": "network", "side": "outputs"}},
            {"code": "surface_unused", "message": "inputs lists 'idle', which no boundary reads", "category": "client", "detail": {"side": "inputs", "target": "idle"}},
            {"code": "surface_unused", "message": "outputs lists 'stdout', which no boundary writes", "category": "client", "detail": {"side": "outputs", "target": "stdout"}},
            {"code": "boundary_without_surface", "message": "Function 'mute' is a boundary_in that reads nothing; a boundary touches a side of the world", "category": "server", "detail": {"function": "mute"}},
            {"code": "boundary_without_surface", "message": "Function 'peek' is a boundary_out that writes nothing; a boundary that only reads is a reader", "category": "server", "detail": {"function": "peek"}},
            {"code": "boundary_without_surface", "message": "Function 'back' is a boundary_in that reads nothing; a boundary touches a side of the world", "category": "server", "detail": {"function": "back"}},
            {"code": "door_takes_readable", "message": "Door 'door' takes a Models, which a reader in this module returns; the module can read it for itself", "category": "server", "detail": {"function": "door", "type": "Models"}}]
    if got != want:
        bad.append(f"surface faults wrong: {got}")
    open_ = validate(_module("module m\n  boundary_in fn door : (r: str) -> str side_effect reads \"HTTP\"\n"))
    if open_ != [{"code": "surface_undeclared", "message": "Module 'm' has 1 boundary and declares no inputs or outputs, so its surface is open", "category": "client", "detail": {"module": "m"}}]:
        bad.append(f"an open surface is one fault: {open_}")
    open2 = validate(_module("module m\n  boundary_in fn door : (r: str) -> str side_effect reads \"HTTP\"\n  boundary_out fn sink : (s: str) -> bool side_effect writes \"stdout\"\n"))
    if [f["message"] for f in open2] != ["Module 'm' has 2 boundaries and declares no inputs or outputs, so its surface is open"]:
        bad.append(f"an open surface with two boundaries: {open2}")
    skeleton = validate(_module("module m\n  inputs = { \"HTTP\" }\n  outputs = { \"stdout\" }\n  fn f : (r: str) -> str\n"))
    if skeleton != []:
        bad.append(f"a surface declared before its boundaries is not a fault: {skeleton}")
    empty = validate(_module("module m\n  inputs = { }\n  env A : str\n  boundary_in fn c : () -> str side_effect reads \"env:A\" invokes run\n  orchestrator fn run : (r: str) -> str\n"))
    if empty != []:
        bad.append(f"an empty surface is declared, and reading the environment is reading: {empty}")
    clean = validate(_module("module m\n  inputs = { \"HTTP\" }\n  outputs = { \"stdout\" }\n  boundary_in fn door : (r: str) -> str side_effect reads \"HTTP\" invokes run\n  orchestrator fn run : (r: str) -> str invokes sink\n  boundary_out fn sink : (s: str) -> bool side_effect writes \"stdout\"\n"))
    if clean != []:
        bad.append(f"a closed surface should validate clean: {clean}")
    return bad


def _probe_awaited():
    """The awaited word is read and propagates up every call whose answer comes back. A pure fn may carry it: it awaits what it is handed."""
    bad = []
    src = ("module m\n  inputs = { \"HTTP\" }\n  outputs = { \"database\" }\n"
           "  dispatch d = { \"a\" -> fine, \"b\" -> waits }\n"
           "  boundary_in fn door : (r: str) -> str side_effect reads \"HTTP\"\n"
           "  orchestrator fn run : (r: str) -> str invokes d, sink\n"
           "  orchestrator fn run_ok : (r: str) -> str awaited invokes sink\n"
           "  fn fine : (r: str) -> str\n"
           "  fn waits : (r: str) -> str awaited\n"
           "  boundary_out fn sink : (s: str) -> bool awaited side_effect writes \"database\"\n"
           "  chain c = door -> run_ok -> sink\n")
    m = _module(src)
    if [f["awaited"] for f in m["functions"]] != [False, False, True, False, True, True]:
        bad.append(f"awaited read wrong: {[(f['name'], f['awaited']) for f in m['functions']]}")
    got = [f for f in validate(m) if f["code"] in ("unawaited_caller", "awaited_pure")]  # awaited_pure never fires: a pure fn may await what it is handed
    want = [{"code": "unawaited_caller", "message": "Function 'run' calls 'waits', which must be awaited, and is not itself awaited", "category": "server", "detail": {"function": "run", "callee": "waits"}},
            {"code": "unawaited_caller", "message": "Function 'run' calls 'sink', which must be awaited, and is not itself awaited", "category": "server", "detail": {"function": "run", "callee": "sink"}},
            {"code": "unawaited_caller", "message": "Function 'door' calls 'run_ok', which must be awaited, and is not itself awaited", "category": "server", "detail": {"function": "door", "callee": "run_ok"}}]
    if got != want:
        bad.append(f"awaited faults wrong: {got}")
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
    if set(PUBLIC) != {"read_hd", "validate", "render", "reach", "ok", "err", "fault"}:
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


def _probe_layer():
    """A module's layer comes from a closed set, because measures are keyed on it.

    The word was free text and nothing read it, so six values were in use by convention and a
    seventh was one keystroke away. Whether a module's seams run the way a layered system's seams
    run, and whether a module holds a wider spread of the world than its level should, are both
    counted against this word. A measure keyed on a word anyone may coin measures nothing.
    """
    bad = []
    for name in ("foundation", "data", "domain", "application", "ui", "tooling"):
        clean = validate(_module(f"module m\n  layer {name}\n  fn f : (a: str) -> str\n"))
        if [f for f in clean if f["code"] == "unknown_layer"]:
            bad.append(f"{name!r} is in the set and must pass: {clean}")

    coined = validate(_module("module m\n  layer middleware\n  fn f : (a: str) -> str\n"))
    named = [f for f in coined if f["code"] == "unknown_layer"]
    if len(named) != 1:
        bad.append(f"a layer the set does not carry must fault once: {coined}")
    elif "middleware" not in named[0]["message"] or "foundation" not in named[0]["message"]:
        bad.append(f"the fault must name the coined word and the set it is not in: {named[0]['message']}")

    # A module declaring no layer at all is a different fact from one declaring a wrong word, and
    # the existing corpus has modules without one. Silence is not a coined word.
    if [f for f in validate(_module("module m\n  fn f : (a: str) -> str\n")) if f["code"] == "unknown_layer"]:
        bad.append("a module declaring no layer is not declaring a layer the set does not carry")
    return bad


def _probe_reach():
    """`reach` answers a question and holds no opinion.

    For each door, the sides of the world its path touches: directly, where a function on that path
    declares one, and through a seam, where the path crosses into another module's door. It returns
    no verdict, compares nothing against a previous run, and has no threshold to breach. The seam is
    the boundary of responsibility, so this is the information half of an I/O budget with the
    obligation half dropped (ruled 6 October 2026).

    It also says what it could not see. A count over declared seams counts what has been written
    down, and 74 seams existed in the framework's code with one declared, so an answer that did not
    carry its own blind spots would read as a small reach when it is a small declaration.
    """
    bad = []
    callee = _module(
        'module honest-persist\n  layer data\n  inputs = { "caller" }\n  outputs = { "database" }\n'
        '  boundary_in fn open : (t: str) -> str invokes run side_effect reads "caller"\n'
        '  orchestrator fn run : (t: str) -> str invokes write\n'
        '  boundary_out fn write : (t: str) -> bool side_effect writes "database"\n'
    )
    caller = _module(
        'module m\n  layer domain\n  inputs = { "HTTP", "honest-persist", "gone" }\n'
        '  boundary_in fn door : (r: str) -> str side_effect reads "HTTP" invokes run\n'
        '  orchestrator fn run : (r: str) -> str invokes store, far\n'
        '  boundary_out fn store : (r: str) -> bool side_effect writes "honest-persist.open"\n'
        '  boundary_out fn far : (r: str) -> bool side_effect writes "gone.somewhere"\n'
    )
    answer = reach(caller, {"honest-persist": callee})

    if sorted(answer) != ["door"]:
        bad.append(f"one answer per door, and nothing else is a door: {sorted(answer)}")
        return bad
    door = answer["door"]
    if sorted(door["direct"]) != ["HTTP"]:
        bad.append(f"a side on the path itself is direct: {door['direct']}")
    if "caller" in door["direct"] or "caller" in door["through"]:
        bad.append(f"'caller' is the direction a call came from, never a side reached: {door}")
    if sorted(door["through"]) != ["database"]:
        bad.append(f"what the path reaches past a seam is through, and it is the callee's: {door['through']}")
    if door["unfollowed"] != 1:
        bad.append(f"a seam into a module not in hand is counted, never silently dropped: {door}")

    # The callee's own doors are missing from the caller's answer. A caller does not inherit what
    # the callee does; it reaches it, which is why the two sets are kept apart and never summed.
    if "open" in answer:
        bad.append("reach answers for the module it was asked about, not for the ones it reaches")

    # A door hands its input to one orchestrator as a chain or as an invokes; the method allows
    # either, so a path written as a chain is a path. honest-parse writes its as a chain, and
    # reading only invokes answered that its door touches nothing when it touches tree-sitter.
    chained = _module(
        'module c\n  layer foundation\n  inputs = { "tree-sitter" }\n'
        '  boundary_in fn door : (s: bytes) -> str side_effect reads "caller"\n'
        '  orchestrator fn place : (s: bytes) -> str invokes read_it\n'
        '  reader fn read_it : (s: bytes) -> str side_effect reads "tree-sitter"\n'
        '  chain path = door -> place\n'
    )
    if reach(chained, {})["door"]["direct"] != ["tree-sitter"]:
        bad.append(f"a path declared as a chain is a path: {reach(chained, {})}")

    # A side naming a module and no door is a seam at module granularity, and every seam declared
    # before the dot existed is one. Counting the module name as a side of the world answered
    # unfollowed = 0 for a seam nothing followed, which is the exact false comfort the unfollowed
    # count exists to prevent. It is followed into every door of that module and counted apart.
    coarse = _module(
        'module k\n  layer domain\n  inputs = { "honest-persist" }\n'
        '  boundary_in fn door : (r: str) -> str invokes store side_effect reads "caller"\n'
        '  boundary_out fn store : (r: str) -> bool side_effect writes "honest-persist"\n'
    )
    wide = reach(coarse, {"honest-persist": callee})["door"]
    if "honest-persist" in wide["direct"]:
        bad.append(f"a module's name is not a side of the world: {wide}")
    if wide["through"] != ["database"]:
        bad.append(f"a seam with no door is followed into every door of that module: {wide}")
    if wide["without_a_door"] != 1:
        bad.append(f"a seam followed at module granularity is counted apart: {wide}")

    # A bare name is a seam only when a declaration of that name is in hand. Nothing in the format
    # tells a module's name from a side of the world's, so with nothing in hand the honest answer
    # is that the path touches something called honest-persist. Declaring the door removes the
    # ambiguity, which is the argument for the dot that a reader can act on.
    blind_coarse = reach(coarse, {})["door"]
    if blind_coarse["direct"] != ["honest-persist"] or blind_coarse["without_a_door"]:
        bad.append(f"with nothing in hand a bare name cannot be known to be a module: {blind_coarse}")
    dotted = _module(
        'module k\n  layer domain\n  inputs = { "honest-persist" }\n'
        '  boundary_in fn door : (r: str) -> str invokes store side_effect reads "caller"\n'
        '  boundary_out fn store : (r: str) -> bool side_effect writes "honest-persist.open"\n'
    )
    named = reach(dotted, {})["door"]
    if named["direct"] or named["unfollowed"] != 1:
        bad.append(f"a side carrying a door is a seam whether or not the callee is in hand: {named}")

    # A path that re-enters a function already walked answers once rather than forever, and a path
    # that names a function the module does not declare stops there rather than raising. The first
    # is a cycle, which a declaration may legitimately carry; the second is `unknown_link`, which
    # the validator reports and this is not the place to report again.
    looping = _module(
        'module l\n  layer domain\n  inputs = { "network" }\n'
        '  boundary_in fn door : (r: str) -> str invokes run side_effect reads "caller"\n'
        '  orchestrator fn run : (r: str) -> str invokes emit, gone\n'
        '  boundary_out fn emit : (r: str) -> bool invokes run side_effect writes "network"\n'
    )
    answered = reach(looping, {})["door"]
    if answered["direct"] != ["network"]:
        bad.append(f"a cycle is walked once and still answers: {answered}")

    # With no declarations in hand every seam is unfollowed, and the answer says so rather than
    # reporting a reach of one side of the world.
    blind = reach(caller, {})["door"]
    if blind["through"] or blind["unfollowed"] != 2:
        bad.append(f"with nothing in hand, every seam is unfollowed and nothing is reached: {blind}")
    return bad


def _probe_seams():
    """A side string names one thing outside the module, qualified two ways that differ.

    A colon names a kind: env:NAME is an environment variable, store:name is held state, and each
    kind has its own rules. A dot names a path inside the thing: which door of another module this
    side enters. The reader splits on the single dot, and answers "" for both parts when there is
    none, because a field that answers "" in one place and null in another makes a caller check
    twice. A declaration never crosses a module boundary, so nothing here resolves the door; that
    is honest-check's, where both sides are in view.
    """
    bad = []
    src = ('module m\n  inputs = { "honest-parse" : "the parser" }\n  outputs = { "database" }\n'
           '  env DATABASE_URL : str\n'
           '  boundary_in fn door : (r: str) -> str side_effect reads "honest-parse.parse_source"\n'
           '  reader fn pull : () -> str side_effect reads "env:DATABASE_URL"\n'
           '  boundary_out fn sink : (s: str) -> bool side_effect writes "database"\n')
    module = _module(src)
    sides = {f["name"]: f["side_effects"][0] for f in module["functions"]}

    dotted = sides["door"]
    if dotted["target"] != "honest-parse.parse_source":
        bad.append(f"the side keeps its whole text: {dotted}")
    if dotted["module"] != "honest-parse" or dotted["door"] != "parse_source":
        bad.append(f"a dotted target splits into the module and the door: {dotted}")

    kind = sides["pull"]
    if kind["module"] or kind["door"]:
        bad.append(f"a colon names a kind and is not a path, so it splits into nothing: {kind}")

    # The surface lists modules, the side names the door. Agreed 6 October: the door goes on the
    # side effect and the surface stays at module granularity, so a dotted side is matched against
    # the surface by its module half. Comparing the whole string made every seam unlistable: the
    # surface could not name the door without holding the same fact twice.
    seam = _module('module m\n  inputs = { "honest-parse" : "the parser" }\n'
                   '  boundary_in fn door : (r: str) -> str side_effect reads "honest-parse.parse_source"\n')
    if [f["code"] for f in validate(seam)]:
        bad.append(f"a side naming a door is listed by its module, not its whole text: {validate(seam)}")

    unlisted = _module('module m\n  inputs = { "filesystem" }\n'
                       '  boundary_in fn door : (r: str) -> str side_effect reads "honest-parse.parse_source"\n')
    if "surface_unknown" not in [f["code"] for f in validate(unlisted)]:
        bad.append("a seam into a module the surface does not list is still a surface fault")

    plain = sides["sink"]
    if plain["module"] != "" or plain["door"] != "":
        bad.append(f'an unqualified side answers "" for both, never null: {plain}')
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
        "envs": _probe_envs(),
        "handles": _probe_handles(),
        "faults": _probe_faults(),
    "seams": _probe_seams(),
    "reach": _probe_reach(),
    "layer": _probe_layer(),
        "readers": _probe_readers(),
        "stores": _probe_stores(),
        "notes": _probe_notes(),
        "awaited": _probe_awaited(),
        "surface": _probe_surface(),
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
