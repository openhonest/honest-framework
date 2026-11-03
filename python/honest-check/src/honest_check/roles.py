"""honest-check the whole-program orphan-function core (HC-R001), split from core.py so no module is a god-file (L1.17).

The per-rule logic nests here as data exactly as it did in core.py; the exact Diagnostic each
rule produces is pinned by the conformance suite (section 9.2), not by a separately declared
function."""

from honest_parse import line_col, parse, parse_source
from honest_check.constants import _INNER_SCOPES, _ROLE_DECORATORS


def check_roles(sources, declaration):
    """The pure whole-program core of the orphan-function rule HC-R001 (§HC-R001), the
    whole-package counterpart of check_source for the one role rule no single file can decide.

    sources is a list of SourceFile ({path, text}) — the package's code files. declaration is
    the package's parsed .hd module (honest-design's IR, each function carrying a name), or the
    absence value NOTHING (None) when the code has no module .hd. A top-level function is ROLED
    when it carries a role decorator — @link, @recognizer, @boundary, @helper, @orchestrator —
    or when the declaration names it, because every function a .hd declares carries a role
    there. The rule builds the whole-program call graph across every source, computes the set
    reachable from the roled set over that graph, and emits one HC-R001 error for each top-level
    function that is neither roled nor reachable — an orphan auto-generation cannot reach.

    When no function is roled at all — no role decorator anywhere and no declaration — the role
    system is not in use for this package and the rule stands down, returning []: it never
    floods a codebase that has not adopted roles with a finding on every function.

    It opens no file and executes no application code — read_source and read_declaration did the
    reads — and raises nothing: an orphan comes back as a Diagnostic. The per-rule logic nests
    here as data, exactly as check_source and cross_declaration hold their rules.
    """

    def unwrap(top_node):
        """A top-level function and its decorator texts, or (None, []) for a non-function
        top-level node — the same read cross_declaration does. A decorated def wraps the
        function_definition under `definition`."""
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

    def final_name(decorator_text):
        """The final name a decorator names — `boundary` from `@boundary`, `link` from
        `@link(boundary=True)`, `lru_cache` from `@functools.lru_cache(maxsize=1)` — read the
        way decorator_target reads it: drop the `@`, drop any call arguments, and take the last
        dotted segment."""
        head = decorator_text.lstrip("@").strip()
        head = head.split("(", 1)[0]
        return head.rsplit(".", 1)[-1].strip()

    def own_nodes(fdef):
        """The body descendants that belong to the function itself: the search does not descend
        into a nested def or lambda, whose statements are that inner scope's own, so a call in a
        nested helper is not read as this function's (sections 4.2, §HC-R002)."""
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

    def facts_of(source_file):
        """The role facts of each top-level function in one source file: its name, location,
        whether a role decorator makes it roled, and the names it calls. A file that does not
        parse contributes nothing — a parse failure is HC-SYN's finding, not this core's."""
        parsed = parse_source(
            source_file["text"].encode("utf-8"), source_file["path"]
        )
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
                    "roled_by_decorator": any(
                        final_name(decorator) in _ROLE_DECORATORS
                        for decorator in decorators
                    ),
                    "calls": calls_of(fdef),
                }
            )
        return facts

    code_functions = [fact for source in sources for fact in facts_of(source)]
    declared_names = (
        {fn["name"] for fn in declaration["functions"]}
        if declaration is not None
        else set()
    )
    roled = {
        fact["name"]
        for fact in code_functions
        if fact["roled_by_decorator"] or fact["name"] in declared_names
    }

    # Stand-down: no role decorator anywhere and no declaration means the role system is not in
    # use for this package, so nothing is judged (§HC-R001).
    if not roled:
        return []

    call_graph = {}
    for fact in code_functions:
        call_graph.setdefault(fact["name"], set()).update(fact["calls"])

    # The reachable closure: a plain breadth over the whole-program call graph from the roled
    # set, exactly the dispatch/chain reachability already in the repo.
    reachable = set(roled)
    frontier = list(roled)
    while frontier:
        current = frontier.pop()
        for callee in call_graph.get(current, ()):
            if callee not in reachable:
                reachable.add(callee)
                frontier.append(callee)

    def finding(source_location, name):
        return {
            "rule_id": "HC-R001",
            "severity": "error",
            "message": f"'{name}' carries no role and no roled function reaches it, so "
            "auto-generation cannot reach it and no test is generated for it. Give it a role, "
            "or call it from one that has one.",
            "source_location": source_location,
            "context": "",
            "fixable": False,
        }

    return [
        finding(fact["source_location"], fact["name"])
        for fact in code_functions
        if fact["name"] not in roled and fact["name"] not in reachable
    ]


