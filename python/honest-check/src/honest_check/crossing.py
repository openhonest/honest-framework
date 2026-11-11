"""honest-check the whole-package declaration-crossing core (sections HC-R002..HC-REF005), split from core.py so no module is a god-file (L1.17).

The per-rule logic nests here as data exactly as it did in core.py; the exact Diagnostic each
rule produces is pinned by the conformance suite (section 9.2), not by a separately declared
function."""

import ast
from honest_parse import line_col, parse, parse_source, walk
from honest_check.constants import _ABSENCE_ATOMS, _INNER_SCOPES


def cross_declaration(sources, declaration, export_source, rule_ids):
    """The pure core of the declaration-crossing path, the crossing-mode counterpart of
    check_source (sections 4.1, 4.2). It crosses one module's .hd declaration against the
    module's whole package of source files at once and returns the declaration-crossing
    findings as data, running only the crossing rules named in rule_ids — an empty list runs
    all five. It opens no file and executes no application code; read_declaration and
    read_source did the reads. It raises nothing: a disagreement comes back as a Diagnostic.

    The per-rule crossing logic is nested here as data, exactly as check_source holds the
    construction rules, never as a separately declared function.
    """
    declared = {fn["name"]: fn for fn in declaration["functions"]}

    def own_nodes(fdef):
        """The body descendants that belong to the function itself: the search does not
        descend into a nested def or lambda, whose statements are that inner scope's own, so
        a `return None` or a `yield` in a nested helper is not read as this function's
        (sections 4.2, §HC-R004, §HC-R005)."""
        body = fdef.child_by_field_name("body")
        found = []

        def gather(node):
            for child in node.named_children:
                if child.type in _INNER_SCOPES:
                    continue
                found.append(child)
                gather(child)

        gather(body)
        return found

    def is_async(fdef):
        return any(child.type == "async" for child in fdef.children)

    def returns_nothing(fdef):
        """True when the function's own body has an explicit `return None` or a bare
        `return` — the two ways a Python function answers the host nothing outright
        (§HC-R004). A fall-off-the-end is not counted, matching the rule's own test."""
        for node in own_nodes(fdef):
            if node.type != "return_statement":
                continue
            children = node.named_children
            if not children:
                return True
            if children[0].type == "none":
                return True
        return False

    def body_yields(fdef):
        return any(node.type == "yield" for node in own_nodes(fdef))

    def arity(fdef):
        params = fdef.child_by_field_name("parameters")
        return sum(1 for child in params.named_children if child.type != "comment")

    def calls_of(fdef):
        """The names this function calls in its own body — a call whose function is a plain
        identifier (§HC-R002). A call inside a nested def belongs to that inner scope."""
        names = set()
        for node in own_nodes(fdef):
            if node.type != "call":
                continue
            function = node.child_by_field_name("function")
            if function is not None and function.type == "identifier":
                names.add(function.text.decode("utf-8"))
        return names

    def unwrap(top_node):
        """A top-level function and its decorator texts, or (None, []) for a non-function
        top-level node. A decorated def wraps the function_definition under `definition`."""
        if top_node.type == "function_definition":
            return top_node, []
        if top_node.type == "decorated_definition":
            definition = top_node.child_by_field_name("definition")
            if definition is not None and definition.type == "function_definition":
                decorators = [
                    child.text.decode("utf-8")
                    for child in top_node.children
                    if child.type == "decorator"
                ]
                return definition, decorators
        return None, []

    def facts_of(source_file):
        """The code facts of each top-level function in one source file: its name, location,
        async-ness, whether it can answer nothing, whether it yields, whether it is a context
        manager, its own call names and its parameter count. A file that does not parse
        contributes nothing — a parse failure is HC-SYN's finding, not this core's."""
        parsed = parse_source(source_file["text"].encode("utf-8"), source_file["path"])
        if "ok" not in parsed:
            return []
        facts = []
        for top_node in parsed["ok"].root_node.named_children:
            fdef, decorators = unwrap(top_node)
            if fdef is None:
                continue
            name_node = fdef.child_by_field_name("name")
            line, col = line_col(fdef)
            facts.append(
                {
                    "name": name_node.text.decode("utf-8"),
                    "source_location": f"{source_file['path']}:{line}:{col}",
                    "is_async": is_async(fdef),
                    "returns_nothing": returns_nothing(fdef),
                    "yields": body_yields(fdef),
                    "is_context_manager": any(
                        "contextmanager" in decorator for decorator in decorators
                    ),
                    "calls": calls_of(fdef),
                    "arity": arity(fdef),
                }
            )
        return facts

    def literal_all(text):
        """The names a literal `__all__ = [...]` lists in the export source, or None when the
        source carries no literal __all__ to read — absent, or built by a call (§HC-REF005).
        An empty literal list is a declared surface of nothing, which is not None."""
        if not text:
            return None
        parsed = parse_source(text.encode("utf-8"), "exports.py")
        if "ok" not in parsed:
            return None
        for node in walk(parsed["ok"].root_node):
            if node.type != "assignment":
                continue
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left is None or right is None or left.type != "identifier":
                continue
            if left.text.decode("utf-8") != "__all__":
                continue
            if right.type not in ("list", "tuple", "set"):
                return None
            return [
                ast.literal_eval(member.text.decode("utf-8"))
                for member in right.named_children
                if member.type == "string"
            ]
        return None

    code_functions = [fact for source in sources for fact in facts_of(source)]
    defined_names = {fact["name"] for fact in code_functions}

    def finding(rule_id, message, source_location):
        return {
            "rule_id": rule_id,
            "severity": "error",
            "message": message,
            "source_location": source_location,
            "context": "",
            "fixable": False,
        }

    def declared_absence(declaration_fn):
        return any(atom["name"] in _ABSENCE_ATOMS for atom in declaration_fn["ret"])

    def check_r002():
        """A declared boundary_out that calls, in the code, a function the declaration marks
        orchestrator or boundary_in — an output boundary invoking inward (§HC-R002). A callee
        the declaration does not name is skipped."""
        inward = frozenset({"orchestrator", "boundary_in"})
        findings = []
        for fact in code_functions:
            declaration_fn = declared.get(fact["name"])
            if declaration_fn is None or declaration_fn["role"] != "boundary_out":
                continue
            for callee in sorted(fact["calls"]):
                callee_fn = declared.get(callee)
                if callee_fn is None or callee_fn["role"] not in inward:
                    continue
                findings.append(
                    finding(
                        "HC-R002",
                        f"'{fact['name']}' is declared boundary_out and invokes '{callee}', "
                        f"declared {callee_fn['role']}. An output boundary is a terminus: "
                        "return a value the caller acts on, or move the work upstream of the "
                        "boundary.",
                        fact["source_location"],
                    )
                )
        return findings

    def check_r003():
        """A declared function whose code async-ness disagrees with its declared awaited
        (§HC-R003)."""
        findings = []
        for fact in code_functions:
            declaration_fn = declared.get(fact["name"])
            if declaration_fn is None or fact["is_async"] == declaration_fn["awaited"]:
                continue
            findings.append(
                finding(
                    "HC-R003",
                    f"'{fact['name']}' is async def and its declaration does not say awaited."
                    if fact["is_async"]
                    else f"'{fact['name']}' is declared awaited and is a plain def.",
                    fact["source_location"],
                )
            )
        return findings

    def check_r004():
        """A declared function whose code can answer nothing while its card names no absence
        arm, or the reverse (§HC-R004). The default — absent means the card promises an
        answer — is verified against the code, not assumed (P15)."""
        findings = []
        for fact in code_functions:
            declaration_fn = declared.get(fact["name"])
            if declaration_fn is None:
                continue
            if fact["returns_nothing"] == declared_absence(declaration_fn):
                continue
            findings.append(
                finding(
                    "HC-R004",
                    f"'{fact['name']}' can return None and its card names no absence arm. "
                    "Add '| NOTHING' to the return, or stop returning None."
                    if fact["returns_nothing"]
                    else f"'{fact['name']}' is declared to return an absence and never "
                    "returns None. Remove the absence arm, or return None where the answer "
                    "is absent.",
                    fact["source_location"],
                )
            )
        return findings

    def check_r005():
        """A declared function whose body yields while its card returns a value, and which is
        not a context manager (§HC-R005)."""
        findings = []
        for fact in code_functions:
            declaration_fn = declared.get(fact["name"])
            if declaration_fn is None or not fact["yields"] or fact["is_context_manager"]:
                continue
            findings.append(
                finding(
                    "HC-R005",
                    f"'{fact['name']}' is declared and its body yields, so it answers with a "
                    "stream rather than a value. Return a value, or move the laziness into a "
                    "helper this module does not declare.",
                    fact["source_location"],
                )
            )
        return findings

    def check_ref005():
        """The exported and defined surface resolves into the declaration (§HC-REF005): an
        exported name the declaration does not name, or a declared parameter count that
        disagrees with the code. The build order writes the .hd before the code, so a declared
        name the code has not written yet is the allowed lag and passes — the rule is one-
        directional, catching code that runs ahead of the .hd, never a .hd that runs ahead of
        the code. An absent or non-literal __all__ fails the rule rather than passing it."""
        module_root = sources[0]["path"] if sources else "exports.py"
        exported = literal_all(export_source)
        if exported is None:
            return [
                finding(
                    "HC-REF005",
                    "the module publishes no literal export list, so its surface is inferred "
                    "rather than declared and this rule cannot read it. Write the list.",
                    module_root,
                )
            ]
        declared_names = set(declared)
        location_of = {fact["name"]: fact["source_location"] for fact in code_functions}
        arity_of = {fact["name"]: fact["arity"] for fact in code_functions}
        findings = []
        for name in sorted(set(exported) - declared_names):
            findings.append(
                finding(
                    "HC-REF005",
                    f"'{name}' is exported by the module and declared in no .hd. Declare it, "
                    "or stop exporting it.",
                    location_of[name] if name in location_of else module_root,
                )
            )
        for name in sorted(declared_names & defined_names):
            declared_arity = len(declared[name]["params"])
            if arity_of[name] != declared_arity:
                findings.append(
                    finding(
                        "HC-REF005",
                        f"'{name}' is declared with {declared_arity} parameters and defined "
                        f"with {arity_of[name]}.",
                        location_of[name],
                    )
                )
        return findings

    # The crossing dispatch: each selected crossing rule runs once over the whole package.
    # rule_ids is narrowed to CrossingRule members (an empty list runs all five); a rule id
    # the table does not name is not a crossing rule and is skipped, guarded by membership.
    crossing_rules = {
        "HC-R002": check_r002,
        "HC-R003": check_r003,
        "HC-R004": check_r004,
        "HC-R005": check_r005,
        "HC-REF005": check_ref005,
    }
    selected = rule_ids if rule_ids else list(crossing_rules)
    findings = []
    for rule_id in selected:
        if rule_id not in crossing_rules:
            continue
        findings.extend(crossing_rules[rule_id]())
    return findings


