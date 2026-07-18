"""honest-design conformance: the generative proof (the behavioural circle).

Folds `.hd` source into the IR and pins every branch a data file cannot easily reach: both type-value
shapes (record and alias), union types and nested generics, set members with and without a
description, all four function roles and their derived columns, multiple side_effects across the
three directions, invokes, raises written bare and quoted, a route with and without a path, a module
with and without a layer, rules global and scoped, actors and flows, the malformed-source fault, the
Result constructors, reader determinism, and the public surface. Each probe returns a list of
failures; run() aggregates.
"""

from honest_design import err, fault, ok, read_hd, validate
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
    if m["dispatches"] != [{"name": "d", "entries": [{"key": "k", "handler": "h"}, {"key": "j", "handler": "g"}]}]:
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


def _probe_public_surface():
    if set(PUBLIC) != {"read_hd", "validate", "ok", "err", "fault"}:
        return [f"public surface drifted: {PUBLIC}"]
    return []


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
        "validate": _probe_validate(),
        "public_surface": _probe_public_surface(),
    }
    violations = [(name, messages) for name, messages in probes.items() if messages]
    for name, messages in violations:
        print(f"FAIL HD-probe [{name}]: {messages}")
    passed = sum(1 for messages in probes.values() if not messages)
    print(f"HD laws: {passed} passed, {len(violations)} failed, {len(probes)} total")
    return 0 if not violations else 1
