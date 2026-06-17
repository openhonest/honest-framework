"""Role / orchestrator rules (spec §4.2): HC-R001, HC-OR001, HC-OR003.

HC-R001 (orphan function) is gated to files that opt into the role system
(at least one roled function). A tool/utility module with no roles is not
subject to role-reachability; without the gate the rule would flag every
function in such a module (including honest-check's own).
"""
from __future__ import annotations

from itertools import combinations

from honest_check.declgraph import (
    call_graph,
    call_sequence,
    local_function_names,
    role_map,
)
from honest_check.diagnostics import Diagnostic, diagnostic
from honest_check.parse import col_of, find_by_type, line_of, node_text


# --- HC-R001: orphan function ---------------------------------------------


def check_hc_r001(root, src: bytes, path: str) -> list[Diagnostic]:
    roles, nodes = role_map(root, src)
    if not roles:
        return []   # file does not use the role system
    graph = call_graph(root, src)
    reachable = set(roles)
    frontier = list(roles)
    while frontier:
        name = frontier.pop()
        for callee in graph.get(name, set()):
            if callee not in reachable:
                reachable.add(callee)
                frontier.append(callee)
    out: list[Diagnostic] = []
    for orphan in sorted(local_function_names(root, src) - reachable):
        node = nodes.get(orphan)
        if node is None:
            continue
        out.append(diagnostic(
            "HC-R001", "error",
            f"Function '{orphan}' has no declared role and is not reachable from "
            "any roled function. Declare a role (@link/@recognizer/@boundary/"
            "@helper) or remove it.",
            path, line_of(node), col_of(node)))
    return out


# --- HC-OR001: orchestrator calls another orchestrator --------------------


def check_hc_or001(root, src: bytes, path: str) -> list[Diagnostic]:
    roles, nodes = role_map(root, src)
    orchestrators = {n for n, r in roles.items() if r == "orchestrator"}
    out: list[Diagnostic] = []
    for name in orchestrators:
        fn = nodes[name]
        for call in find_by_type(fn, "call"):
            func = call.child_by_field_name("function")
            if func is not None and func.type == "identifier":
                callee = node_text(func, src)
                if callee in orchestrators and callee != name:
                    out.append(diagnostic(
                        "HC-OR001", "error",
                        f"Orchestrator '{name}' calls orchestrator '{callee}'. "
                        "Orchestrators do not compose — extract a pure helper or "
                        "a chain.",
                        path, line_of(call), col_of(call)))
    return out


# --- HC-OR003: suspected duplication between orchestrators -----------------


def _lcs_length(a: list, b: list) -> int:
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    best = 0
    for x in a:
        curr = [0] * (len(b) + 1)
        for j, y in enumerate(b, start=1):
            curr[j] = prev[j - 1] + 1 if x == y else max(prev[j], curr[j - 1])
            best = max(best, curr[j])
        prev = curr
    return best


def check_hc_or003(root, src: bytes, path: str, min_run: int = 3) -> list[Diagnostic]:
    roles, nodes = role_map(root, src)
    orchestrators = [n for n, r in roles.items() if r == "orchestrator"]
    sequences = {n: call_sequence(nodes[n], src) for n in orchestrators}
    out: list[Diagnostic] = []
    for a, b in combinations(sorted(orchestrators), 2):
        shared = _lcs_length(sequences[a], sequences[b])
        if shared >= min_run:
            out.append(diagnostic(
                "HC-OR003", "warning",
                f"Orchestrators '{a}' and '{b}' share {shared} operations. "
                "Consider extracting the shared sequence as a helper or chain.",
                path, line_of(nodes[b]), col_of(nodes[b])))
    return out


ROLE_CHECKS = [
    check_hc_r001,
    check_hc_or001,
    check_hc_or003,
]
