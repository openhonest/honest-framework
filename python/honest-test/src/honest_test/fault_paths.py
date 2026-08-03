"""Deliberate fault-path generation (section 9.2): read a link's guards and construct inputs that
trigger its fault exits.

A fault exit is a point where a link returns `err`. Strategy 1 (section 9.2.1) reads the guard: for a
fault exit whose guard is a solvable comparison of a manifest field against an integer, it produces a
manifest fragment that satisfies the guard. A guard that turns on external state - it calls something
whose result no manifest can force - cannot be reached by any input and is disclosed by name, never
silently dropped (section 9.2.2). A guard that is pure over the manifest but not one strategy 1 solves
is deferred to perturbation (strategy 2). The condition is read from the code that already holds it; a
link is never asked to declare its failures a second time.
"""

from honest_parse import node_text, parse_python, walk
from honest_type.chains import execute_chain, link_meta
from honest_type.recognizers import is_bounded, members, recognize

from honest_test.adversarial import adversarial_neighbours
from honest_test.enumeration import enumerate_sets

# Operator token -> a value that makes `manifest[field] <op> literal` true, keyed by the tree-sitter
# operator node type. Numeric comparison guards only; a value strategy 1 can solve by reading.
_TRIGGER = {
    "<=": lambda literal: literal,
    "<": lambda literal: literal - 1,
    ">=": lambda literal: literal,
    ">": lambda literal: literal + 1,
    "==": lambda literal: literal,
    "!=": lambda literal: literal + 1,
}


def _string_value(node, source) -> str:
    """The text of a string literal node with its surrounding quotes stripped."""
    return node_text(node, source)[1:-1]


def _has_call(node) -> bool:
    """Whether a guard subtree calls anything - the signal it turns on external state (section 9.2.2)."""
    return any(descendant.type == "call" for descendant in walk(node))


def _returns_err(consequence, source) -> bool:
    """Whether an if-consequence returns a dict carrying an `err` key - the shape of a fault exit."""
    return any(
        node.type == "pair" and node.child_by_field_name("key").type == "string" and _string_value(node.child_by_field_name("key"), source) == "err"
        for node in walk(consequence)
    )


def _fault_code(consequence, source) -> str:
    """The fault code an err-returning consequence carries: the first string argument of its `fault(...)`
    call, or the empty string when it returns an err with no fault call."""
    for node in walk(consequence):
        if node.type == "call" and node_text(node.child_by_field_name("function"), source) == "fault":
            for arg in node.child_by_field_name("arguments").named_children:
                if arg.type == "string":
                    return _string_value(arg, source)
    return ""


def _manifest_field(node, source):
    """The field name when `node` is `manifest["field"]`, else None."""
    if node.type != "subscript":
        return None
    key = node.child_by_field_name("subscript")
    if node_text(node.child_by_field_name("value"), source) != "manifest" or key.type != "string":
        return None
    return _string_value(key, source)


def _solved_trigger(condition, source):
    """A {field: value} fragment that makes a comparison guard true, or None when the guard is not a
    solvable comparison of `manifest["field"]` against an integer literal. A non-comparison guard is
    rejected by the shape checks below (a wrong child count, or an operator not in the trigger table),
    so it needs no separate type guard."""
    parts = condition.children
    if len(parts) != 3:
        return None
    left, operator, right = parts
    field = _manifest_field(left, source)
    if field is None or operator.type not in _TRIGGER or right.type != "integer":
        return None
    return {field: _TRIGGER[operator.type](int(node_text(right, source)))}


def _fault_ifs(source_bytes):
    """Every if_statement whose consequence returns an err fault."""
    root = parse_python(source_bytes).root_node
    return [
        node
        for node in walk(root)
        if node.type == "if_statement" and _returns_err(node.child_by_field_name("consequence"), source_bytes)
    ]


# Edge values a field is pushed to when its guard cannot be read (strategy 2): the values most likely
# to trip an unread numeric or length guard. Every edge is tried on every field - an edge of the wrong
# type is simply rejected at the door and trips nothing, so no runtime type check is needed to choose.
_EDGES = (0, -1, 1_000_000, "", "x" * 1000)


def perturbations(manifest) -> list:
    """Strategy 2 (section 9.2.1): a passing manifest perturbed one field at a time - the field omitted,
    and pushed to each edge value - so the chain can be run on each and the fault exits that trip
    recorded. Pure: it yields the variant manifests; running them is the caller's job."""
    variants = []
    for field in manifest:
        variants.append({key: value for key, value in manifest.items() if key != field})
        for edge in _EDGES:
            variants.append({**manifest, field: edge})
    return variants


def seam_breakers(links) -> list:
    """Strategy 3 (section 9.2.1): for each adjacent pair, a hand-off value the downstream rejects - a
    near-miss of a member its accepts vocabulary declares. Feeding it to the downstream trips the
    hand-off fault. Pure; running it is the caller's job. A pair whose downstream declares no accepts
    vocabulary, or a type that is not a bounded Set, has no readable seam and yields nothing."""
    breakers = []
    for index in range(len(links) - 1):
        vocab = link_meta(links[index + 1])["accepts"]
        if vocab is None:
            continue
        for name, recognizer in vocab["base_types"].items():
            if not is_bounded(recognizer):
                continue
            member = min(members(recognizer))
            breaker = min(neighbour for neighbour in adversarial_neighbours(member) if not recognize(neighbour, recognizer))
            breakers.append({"seam": index, "manifest": {name: breaker}})
    return breakers


def function_source(source, name) -> str:
    """The source text of the top-level function named `name` within `source`, or the empty string when
    there is none. Used to hand each chain link its own source to read for fault exits."""
    root = parse_python(source.encode("utf-8")).root_node
    for node in walk(root):
        if node.type == "function_definition" and node_text(node.child_by_field_name("name"), source.encode("utf-8")) == name:
            return node_text(node, source.encode("utf-8"))
    return ""


def _tripped_code(links, manifest):
    """The fault code a candidate manifest trips when run through the chain, or None when the chain runs
    clean. A malformed candidate that makes a link raise (a field it reads is missing) trips nothing
    cleanly, so the raise is caught here - this is the boundary where a bad candidate becomes no-result."""
    try:  # honest: disable HC-P002: the boundary where a malformed generated candidate that makes a link raise becomes no clean fault trip
        result = execute_chain(links, manifest)
    except Exception:
        return None
    return result["err"]["code"] if "err" in result else None


def fault_coverage(links, sources, vocab, bind) -> dict:
    """Chain fault coverage (section 9.2): the input-reachable fault exits across the links (strategy 1's
    reachable and deferred), how many are exercised by running the generated candidates - the read-guard
    triggers, the field perturbations (strategy 2), and the seam breakers (strategy 3) - and the
    unreachable exits disclosed with their reason. `sources` is each link's own source, in order."""
    reachable = set()
    unreachable = []
    triggers = []
    for source in sources:
        exits = fault_exits(source)
        for exit_point in exits["reachable"]:
            reachable.add(exit_point["code"])
            triggers.append(exit_point["trigger"])
        for exit_point in exits["deferred"]:
            reachable.add(exit_point["code"])
        unreachable.extend(exits["unreachable"])
    # enumerate_sets always yields at least one manifest (the empty one for a vocabulary with no bounded
    # Sets), so every base below is a real starting point - no empty-fallback is needed.
    manifests = enumerate_sets(vocab, bind)
    candidates = (
        [{**base, **trigger} for base in manifests for trigger in triggers]
        + [variant for base in manifests for variant in perturbations(base)]
        + [breaker["manifest"] for breaker in seam_breakers(links)]
    )
    tripped = {code for code in (_tripped_code(links, candidate) for candidate in candidates) if code is not None}
    return {
        "input_reachable": sorted(reachable),
        "exercised": sorted(tripped & reachable),
        "unreachable": unreachable,
    }


def fault_exits(source) -> dict:
    """Read a link's fault exits (section 9.2). Returns three lists: `reachable` fault exits, each with a
    trigger fragment strategy 1 solved from the guard; `deferred` fault exits, pure over the manifest but
    not solved by reading, left to perturbation (strategy 2); and `unreachable` fault exits, whose guard
    turns on external state so no input can reach them, each disclosed with its reason."""
    source_bytes = source.encode("utf-8")
    reachable = []
    deferred = []
    unreachable = []
    for if_node in _fault_ifs(source_bytes):
        code = _fault_code(if_node.child_by_field_name("consequence"), source_bytes)
        condition = if_node.child_by_field_name("condition")
        if _has_call(condition):
            unreachable.append({"code": code, "reason": "state-dependent"})
            continue
        trigger = _solved_trigger(condition, source_bytes)
        if trigger is None:
            deferred.append({"code": code, "reason": "needs-perturbation"})
            continue
        reachable.append({"code": code, "trigger": trigger})
    return {"reachable": reachable, "deferred": deferred, "unreachable": unreachable}
