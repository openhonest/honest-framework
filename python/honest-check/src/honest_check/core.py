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

from honest_parse import parse_source, walk

from honest_check.nodes import import_aliases
from honest_check.rules_construction import check_construction
from honest_check.rules_per_file import check_per_file
from honest_check.suppress import apply_suppression


def check_source(source, path, rule_config, declaration):
    # The function-name -> role map the boundary rules consult on the error path. Built once
    # here from the module's parsed .hd (honest-design's IR), and empty when declaration is
    # NOTHING (Python None, the absence arm) — an adopter codebase or a loose snippet.
    roles_by_name = (
        {function["name"]: function["role"] for function in declaration["functions"]}
        if declaration is not None
        else {}
    )
    parsed = parse_source(source.encode("utf-8"), path)
    if "ok" not in parsed:
        error = parsed["err"]

        def syntax_location():
            detail = error["detail"]
            return f"{path}:{detail['line']}:{detail['col']}"

        if error["code"] == "syntax_error":
            return [
                {
                    "rule_id": "HC-SYN",
                    "severity": "error",
                    "message": error["message"],
                    "source_location": syntax_location(),
                    "context": "",
                    "fixable": False,
                }
            ]
        return []

    root = parsed["ok"].root_node
    nodes = walk(root)
    # import_aliases reads ctx["nodes"] to build the alias map, so ctx is assembled first
    # and the aliases added once resolved; the key is set exactly once, never a placeholder.
    ctx = {
        "root": root,
        "nodes": nodes,
        "roles": roles_by_name,
        "source": source,
        "path": path,
        "rule_config": rule_config,
    }
    ctx["aliases"] = import_aliases(ctx)
    return apply_suppression(ctx, check_per_file(ctx) + check_construction(ctx))


def pair_source(path, text):
    """Join one discovered path with its already-read text into a SourceFile (§4.1).

    run_check calls this once per discovered file in crossing mode, after discover_files
    gave the path and read_source gave the text, to assemble the list<SourceFile> whole-
    package view cross_declaration takes. It reads nothing and decides nothing — it only
    joins the two values into the record the crossing core is fed.
    """
    return {"path": path, "text": text}
