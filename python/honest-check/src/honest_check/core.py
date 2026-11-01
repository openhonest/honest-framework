"""check_source — the pure core of the checker (sections 3.3, 3.4, 4.1).

It parses one source unit under the grammar honest-parse detects from the path's
extension, resolves the framework's own construction call sites, builds the declaration
graph, and runs the rules this layer owns over that graph, returning findings as data. It
opens no file, executes no application code, and never raises for a violation: a violation
comes back as a Diagnostic.

The rule engine is data inside this function — nested resolvers, nested per-construct
handlers, and the module-level tables below — never a module-level per-rule def. The exact
Diagnostic each rule produces is pinned by the conformance suite (section 9.2), not by a
separately declared function.
"""

import ast
import itertools

from honest_parse import line_col, parse_source, walk

# A class is permitted only as a subclass of one of these (section 4.1, HC-P003). A bare
# class implicitly inherits object, which is not approved, so it is a violation.
_APPROVED_BASES = frozenset(
    {"TypedDict", "Protocol", "ABC", "Exception", "BaseException", "Error"}
)

# The framework construction call sites this layer recognizes as top-level constructs
# (section 4.1). composed() is not here: it is only meaningful inside a vocabulary's
# composed_types, where the vocabulary handler reaches it, so a standalone composed() call
# in the walk is skipped rather than processed twice.
_CONSTRUCTORS = frozenset({"vocabulary", "chain", "state_machine"})


def check_source(source, path, rule_config):
    parsed = parse_source(source.encode("utf-8"), path)
    if "ok" not in parsed:
        error = parsed["err"]

        def syntax_location():
            detail = error.get("detail", {})
            line = detail.get("line", 1)
            col = detail.get("col", 1)
            return f"{path}:{line}:{col}"

        if error.get("code") == "syntax_error":
            return [
                {
                    "rule_id": "HC-SYN",
                    "severity": "error",
                    "message": error.get("message", "source does not parse"),
                    "source_location": syntax_location(),
                    "context": "",
                    "fixable": False,
                }
            ]
        return []

    root = parsed["ok"].root_node
    nodes = walk(root)

    def diagnostic(rule_id, severity, message, node):
        line, col = line_col(node)
        return {
            "rule_id": rule_id,
            "severity": severity,
            "message": message,
            "source_location": f"{path}:{line}:{col}",
            "context": node.text.decode("utf-8", "replace").splitlines()[0]
            if node.text
            else "",
            "fixable": False,
        }

    def literal_string(node):
        """The Python string a `string` node spells, quotes stripped."""
        return ast.literal_eval(node.text.decode("utf-8"))

    def string_members(node):
        """The string values a set/list/tuple node holds, in source order."""
        return [
            literal_string(child)
            for child in node.named_children
            if child.type == "string"
        ]

    def call_arguments(call_node):
        """The (positional nodes, keyword name -> value node) of a call."""
        argument_list = call_node.child_by_field_name("arguments")
        positionals = []
        keywords = {}
        if argument_list is None:
            return positionals, keywords
        for child in argument_list.named_children:
            if child.type == "keyword_argument":
                name = child.child_by_field_name("name").text.decode("utf-8")
                keywords[name] = child.child_by_field_name("value")
            else:
                positionals.append(child)
        return positionals, keywords

    def resolve_aliases():
        """Map each local name bound by a honest_type import to its canonical constructor
        name (section 3.3), so a call under an alias resolves to the real constructor."""
        aliases = {}
        for node in nodes:
            if node.type != "import_from_statement":
                continue
            module = node.child_by_field_name("module_name")
            if module is None or module.text.decode("utf-8") != "honest_type":
                continue
            for imported in node.children_by_field_name("name"):
                if imported.type == "aliased_import":
                    canonical = imported.child_by_field_name("name").text.decode("utf-8")
                    local = imported.child_by_field_name("alias").text.decode("utf-8")
                    aliases[local] = canonical
                else:
                    name = imported.text.decode("utf-8")
                    aliases[name] = name
        return aliases

    aliases = resolve_aliases()

    def canonical_name(call_node):
        """The constructor name a call resolves to, or None when the call is not a framework
        constructor. A direct constructor-name call counts, and an aliased one resolves
        through the import (section 3.3)."""
        function = call_node.child_by_field_name("function")
        if function is None or function.type != "identifier":
            return None
        name = function.text.decode("utf-8")
        if name in aliases:
            return aliases[name]
        if name in _CONSTRUCTORS:
            return name
        return None

    def base_types_of(dictionary_node):
        """The base-type map of a vocabulary's first argument: name -> (kind, members).
        kind is 'set' with a frozenset of members, or 'predicate' with None (a lambda or any
        other opaque recognizer honest-check cannot run)."""
        base_types = {}
        for pair in dictionary_node.named_children:
            if pair.type != "pair":
                continue
            name = literal_string(pair.child_by_field_name("key"))
            value = pair.child_by_field_name("value")
            if value.type == "set":
                base_types[name] = ("set", frozenset(string_members(value)))
            else:
                base_types[name] = ("predicate", None)
        return base_types

    def check_vocabulary(call_node):
        """HC003 overlap, HC011 catch-all predicate, and HC006 unknown composed base
        (section 4.1)."""
        findings = []
        positionals, keywords = call_arguments(call_node)
        if not positionals or positionals[0].type != "dictionary":
            return findings
        base_types = base_types_of(positionals[0])

        for a, b in itertools.combinations(base_types, 2):
            kind_a, members_a = base_types[a]
            kind_b, members_b = base_types[b]
            if kind_a == "set" and kind_b == "set":
                overlap = members_a & members_b
                if overlap:
                    findings.append(
                        diagnostic(
                            "HC003",
                            "error",
                            f"Types {a!r} and {b!r} share values: {sorted(overlap)}",
                            call_node,
                        )
                    )
            else:
                findings.append(
                    diagnostic(
                        "HC003",
                        "info",
                        f"Types {a!r} and {b!r} may overlap on a value — "
                        "verified by honest-test",
                        call_node,
                    )
                )

        for name, (kind, _members) in base_types.items():
            if kind == "predicate":
                findings.append(
                    diagnostic(
                        "HC011",
                        "info",
                        f"Predicate recognizer {name!r} may be a catch-all — "
                        "verified by honest-test",
                        call_node,
                    )
                )

        composed_list = keywords.get("composed_types")
        if composed_list is not None:
            for child in composed_list.named_children:
                if child.type == "call" and canonical_name(child) == "composed":
                    findings.extend(check_composed(child, base_types))
        return findings

    def check_composed(call_node, base_types):
        """HC006: a composed type whose requires or captures names a base the vocabulary does
        not declare (section 4.1)."""
        findings = []
        positionals, _keywords = call_arguments(call_node)
        if len(positionals) < 2 or positionals[1].type != "dictionary":
            return findings
        for pair in positionals[1].named_children:
            if pair.type != "pair":
                continue
            required = literal_string(pair.child_by_field_name("key"))
            if required not in base_types:
                findings.append(
                    diagnostic(
                        "HC006",
                        "error",
                        f"Composed type requires unknown base type {required!r}",
                        call_node,
                    )
                )
        if len(positionals) >= 3 and positionals[2].type == "string":
            captured = literal_string(positionals[2])
            if captured not in base_types:
                findings.append(
                    diagnostic(
                        "HC006",
                        "error",
                        f"Composed type captures unknown base type {captured!r}",
                        call_node,
                    )
                )
        return findings

    def check_chain(call_node):
        """HC007: a chain() constructed with no links is empty (section 4.1)."""
        positionals, _keywords = call_arguments(call_node)
        if not positionals:
            return [diagnostic("HC007", "error", "Chain has no links", call_node)]
        return []

    def check_state_machine(call_node):
        """HC-SM01/02/05: a transition state or event, or the initial state, not in its
        vocabulary (section 4.1)."""
        findings = []
        positionals, _keywords = call_arguments(call_node)
        if len(positionals) < 4:
            return findings
        states = set(string_members(positionals[0]))
        events = set(string_members(positionals[1]))
        transitions = positionals[2]
        initial = literal_string(positionals[3]) if positionals[3].type == "string" else None

        for pair in transitions.named_children:
            if pair.type != "pair":
                continue
            key = pair.child_by_field_name("key")
            if key.type != "tuple":
                continue
            members = string_members(key)
            if len(members) < 2:
                continue
            state, event = members[0], members[1]
            if state not in states:
                findings.append(
                    diagnostic(
                        "HC-SM01",
                        "error",
                        f"State {state!r} in transition table not in states vocabulary",
                        call_node,
                    )
                )
            if event not in events:
                findings.append(
                    diagnostic(
                        "HC-SM02",
                        "error",
                        f"Event {event!r} in transition table not in events vocabulary",
                        call_node,
                    )
                )
        if initial is not None and initial not in states:
            findings.append(
                diagnostic(
                    "HC-SM05",
                    "error",
                    f"Initial state {initial!r} not in states vocabulary",
                    call_node,
                )
            )
        return findings

    # The construction dispatch: a call that resolves to a framework constructor runs the
    # matching handler; a call that resolves to no constructor is skipped, the expected and
    # common case for ordinary application calls, not a fault.
    construction_handlers = {
        "vocabulary": check_vocabulary,
        "chain": check_chain,
        "state_machine": check_state_machine,
    }

    def check_classes():
        """HC-P003: a bare class, or a class inheriting a non-approved base (section 4.1)."""
        findings = []
        for node in nodes:
            if node.type != "class_definition":
                continue
            name_node = node.child_by_field_name("name")
            name = name_node.text.decode("utf-8") if name_node else "<anonymous>"
            superclasses = node.child_by_field_name("superclasses")
            bases = (
                [c for c in superclasses.named_children]
                if superclasses is not None
                else []
            )
            if not bases:
                findings.append(
                    diagnostic(
                        "HC-P003",
                        "error",
                        f"Class {name!r} has no declared base. Use a TypedDict for data "
                        "shapes or a pure function.",
                        node,
                    )
                )
                continue
            for base in bases:
                if base.text.decode("utf-8") not in _APPROVED_BASES:
                    findings.append(
                        diagnostic(
                            "HC-P003",
                            "error",
                            f"Class {name!r} inherits from {base.text.decode('utf-8')!r}. "
                            "Use composition over inheritance.",
                            node,
                        )
                    )
        return findings

    diagnostics = list(check_classes())
    for node in nodes:
        if node.type != "call":
            continue
        canonical = canonical_name(node)
        if canonical not in construction_handlers:
            continue
        diagnostics.extend(construction_handlers[canonical](node))
    return diagnostics
