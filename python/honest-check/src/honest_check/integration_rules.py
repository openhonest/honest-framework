"""Integration rules: auth, features, roles, orchestrators, and persisted-state writes.

Cross-module rules that check how a file wires honest-auth, honest-features, function
roles, and honest-state/persist together — each riding on the shared declaration graph.
"""

from itertools import combinations
from honest_check.declgraph import (
    authorizing_links,
    feature_state_calls,
    feature_vocabulary,
    function_calls,
    function_role,
    functions_by_name,
    handler_table_dispatches,
    is_provider_registered,
    module_dict_keys,
    resolve_aliases,
)
from honest_check.diagnostics import (
    Diagnostic,
    diagnostic,
)
from honest_check.watchlists import (
    PERSISTED_WRITE_WATCH_LIST,
    matches_watchlist,
)
from honest_parse import (
    line_col,
    node_text,
    walk,
)
from honest_check._rule_helpers import (
    _OR003_MIN_RUN,
    _enclosing_function,
    _is_boundary_function,
    _longest_common_run,
    _orchestrator_call_sequence,
    _qualified_call_name,
)


def check_hc_r001(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-R001 — orphan function: no declared role and not reachable from a roled one.

    Gated to files that declare at least one role, so plain non-framework modules are
    not swept. Auto-generation reaches roled functions and, transitively, the helpers
    they call; anything left over has no test story.
    """
    functions = functions_by_name(root, source)
    roled = {name for name, node in functions.items() if function_role(node, source) is not None}
    if not roled:
        return []
    calls = {name: function_calls(node, source) for name, node in functions.items()}
    reachable = set(roled)
    frontier = list(roled)
    while frontier:
        nxt: list[str] = []
        for caller in frontier:
            for callee in calls.get(caller, set()):
                if callee in functions and callee not in reachable:
                    reachable.add(callee)
                    nxt.append(callee)
        frontier = nxt
    out: list[Diagnostic] = []
    for name, node in functions.items():
        if name in reachable:
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC-R001",
                "error",
                path,
                line,
                col,
                f"Function '{name}' has no declared role and is not called by any roled "
                "function. Declare a role (@link / @recognizer / @boundary / @helper) or remove it.",
            )
        )
    return out


def check_hc_or001(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-OR001 — an orchestrator calls another orchestrator (error). They do not compose."""
    functions = functions_by_name(root, source)
    orchestrators = {
        name for name, node in functions.items() if function_role(node, source) == "orchestrator"
    }
    out: list[Diagnostic] = []
    for name in sorted(orchestrators):
        for callee in sorted(function_calls(functions[name], source)):
            if callee in orchestrators:
                line, col = line_col(functions[name])
                out.append(
                    diagnostic(
                        "HC-OR001",
                        "error",
                        path,
                        line,
                        col,
                        f"Orchestrator '{name}' calls orchestrator '{callee}'. Orchestrators "
                        "do not compose — extract shared logic as a pure helper or a chain.",
                    )
                )
    return out


def check_hc_a001(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-A001 — links declare authorizes=True but no AuthProvider is registered (warning)."""
    aliases = resolve_aliases(root, source)
    links = authorizing_links(root, source, aliases)
    if not links:
        return []
    if is_provider_registered(root, source):
        return []
    line, col = line_col(links[0][1])
    names = sorted(name for name, _ in links)
    return [
        diagnostic(
            "HC-A001",
            "warning",
            path,
            line,
            col,
            f"No AuthProvider registered, but these links declare authorizes=True and "
            f"cannot be verified: {names}. Register a provider, or declare authorizes=False.",
        )
    ]


def check_hc_a002(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-A002 — an authorizing link does not use the boundary-resolved actor (error).

    Identity is resolved at the boundary (honest-auth) and passed inward as `actor`. An authorizing
    link must use that boundary actor; one that does not is sourcing identity from request input,
    which is forgeable.
    """
    aliases = resolve_aliases(root, source)
    links = authorizing_links(root, source, aliases)
    if not links:
        return []
    if not is_provider_registered(root, source):
        return []  # HC-A001 handles the no-provider case
    out: list[Diagnostic] = []
    for name, node in links:
        body = node.child_by_field_name("body")
        uses_actor = body is not None and any(
            sub.type == "identifier" and node_text(sub, source) == "actor"
            for sub in walk(body)
        )
        if uses_actor:
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC-A002",
                "error",
                path,
                line,
                col,
                f"Link '{name}' declares authorizes=True but does not use the boundary-resolved "
                "actor ('actor'). Actor identity must come from the boundary, not be trusted from "
                "request input.",
            )
        )
    return out


def check_hc_hf001(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-HF001 — feature_state references a flag not declared in FEATURES (error, honest-features section 7).

    Every feature_state(state, "flag") call must name a flag declared in the module's FEATURES
    vocabulary; an undeclared flag raises KeyError at runtime. Checked only when FEATURES is a readable
    module-scope dict literal — there is nothing to verify against otherwise.
    """
    vocab = feature_vocabulary(root, source)
    if not vocab:
        return []
    out: list[Diagnostic] = []
    for flag, node in feature_state_calls(root, source):
        if flag in vocab:
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC-HF001",
                "error",
                path,
                line,
                col,
                f"feature_state references '{flag}', which is not a declared flag in FEATURES.",
            )
        )
    return out


def check_hc_hf002(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-HF002 — a handler table is missing an entry for a declared flag state (warning, honest-features section 7).

    A handler table keyed on feature_state(state, "flag") must declare a handler for every state in
    FEATURES["flag"]["states"]; a missing entry raises KeyError at dispatch time when the flag enters
    that state. Checked when both the flag and the table are readable module-scope literals.
    """
    vocab = feature_vocabulary(root, source)
    if not vocab:
        return []
    out: list[Diagnostic] = []
    for table_name, flag, node in handler_table_dispatches(root, source):
        if flag not in vocab:
            continue  # HC-HF001 handles the undeclared flag
        keys = module_dict_keys(table_name, root, source)
        if keys is None:
            continue  # the table is not a module dict literal — nothing to verify against
        missing = sorted(vocab[flag] - keys)
        if not missing:
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC-HF002",
                "warning",
                path,
                line,
                col,
                f"Handler table '{table_name}' is missing an entry for these states of '{flag}': {missing}.",
            )
        )
    return out


def check_hc_or003(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-OR003 — two orchestrators share a run of consecutive operations (warning, soft)."""
    functions = functions_by_name(root, source)
    orchestrators = {
        name: node for name, node in functions.items() if function_role(node, source) == "orchestrator"
    }
    sequences = {
        name: _orchestrator_call_sequence(node, source) for name, node in orchestrators.items()
    }
    out: list[Diagnostic] = []
    for first, second in combinations(sorted(orchestrators), 2):
        run = _longest_common_run(sequences[first], sequences[second])
        if run < _OR003_MIN_RUN:
            continue
        line, col = line_col(orchestrators[first])
        out.append(
            diagnostic(
                "HC-OR003",
                "warning",
                path,
                line,
                col,
                f"Orchestrators '{first}' and '{second}' share {run} consecutive operations. "
                "Consider extracting the shared sequence as a pure helper (if side-effect-free) "
                "or a chain (if I/O is involved). Orchestrators are not composable (HC-OR001).",
            )
        )
    return out


def check_hc_st001(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-ST001 — a write to persisted state outside an I/O-boundary function (honest-state section 3,
    the single-mutator law: persisted domain state is written only by an honest-persist boundary
    write). honest-persist is itself that boundary layer, so its own source is not policed here."""
    if "honest_persist" in path or "honest-persist" in path:
        return []
    writes = PERSISTED_WRITE_WATCH_LIST["python"]
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "call":
            continue
        name = _qualified_call_name(node, source)
        if not matches_watchlist(name, writes):
            continue
        enclosing = _enclosing_function(node)
        if enclosing is None or _is_boundary_function(enclosing, source):
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC-ST001",
                "error",
                path,
                line,
                col,
                f"Persisted-state write '{name}' outside an I/O-boundary function. The single "
                "mutator for persisted state is an honest-persist boundary write — move it to a "
                "boundary (@boundary or @link(boundary=True)). See honest-state section 3.",
            )
        )
    return out
