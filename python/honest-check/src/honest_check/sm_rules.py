"""Static state-machine rules (spec §4.2): HC-SM03, HC-SM04, HC-SM06.

HC-SM03 (unreachable state) and HC-SM04 (dead state) are graph properties of
the transition table. HC-SM06 (transition writes to an undeclared state field)
inspects transition functions when `state_fields` is declared. All build on
extract_state_machine from the declaration graph.
"""
from __future__ import annotations

from honest_check.declgraph import extract_state_machine, find_constructor_calls
from honest_check.diagnostics import Diagnostic, diagnostic
from honest_check.parse import col_of, find_by_type, line_of, node_text


def _state_machines(root, src: bytes):
    return [extract_state_machine(call, src)
            for ctor, call in find_constructor_calls(root, src)
            if ctor == "state_machine"]


# --- HC-SM03 / HC-SM04 ----------------------------------------------------


def _reachable(initial: str, transitions) -> set:
    adjacency: dict = {}
    for t in transitions:
        adjacency.setdefault(t["state"], []).append(t["target"])
    reached = {initial}
    frontier = [initial]
    while frontier:
        state = frontier.pop()
        for target in adjacency.get(state, []):
            if target is not None and target not in reached:
                reached.add(target)
                frontier.append(target)
    return reached


def check_hc_sm03_sm04(root, src: bytes, path: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for machine in _state_machines(root, src):
        states = machine["states"]
        if not states:
            continue
        loc = machine["node"]
        transitions = machine["transitions"]
        terminal = machine["terminal"]
        sources = {t["state"] for t in transitions}

        # HC-SM04: a state with no outgoing transition that is not terminal.
        for state in sorted(states):
            if state not in sources and state not in terminal:
                out.append(diagnostic(
                    "HC-SM04", "warning",
                    f"State '{state}' has no outgoing transitions and is not "
                    "declared terminal.",
                    path, line_of(loc), col_of(loc)))

        # HC-SM03: unreachable state — only when all targets are known (no
        # function-valued transitions, whose targets cannot be read statically).
        initial = machine["initial"]
        targets_known = all(t["target"] is not None for t in transitions)
        if initial is not None and targets_known:
            reached = _reachable(initial, transitions)
            for state in sorted(states):
                if state != initial and state not in reached:
                    out.append(diagnostic(
                        "HC-SM03", "warning",
                        f"State '{state}' is unreachable.",
                        path, line_of(loc), col_of(loc)))
    return out


# --- HC-SM06: transition writes to an undeclared state field --------------


def _written_fields(value_node, src: bytes) -> set:
    """String keys written in dict literals inside a transition function body.
    `{**state, 'status': x}` -> {'status'}; the spread is ignored."""
    if value_node is None:
        return set()
    fields: set = set()
    for dnode in find_by_type(value_node, "dictionary"):
        for pair in dnode.named_children:
            if pair.type != "pair":
                continue   # dictionary_splat (**state) is skipped
            key = pair.child_by_field_name("key")
            if key is not None and key.type == "string":
                parts = [node_text(c, src) for c in key.children if c.type == "string_content"]
                fields.add("".join(parts))
    return fields


def check_hc_sm06(root, src: bytes, path: str) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for machine in _state_machines(root, src):
        declared = machine["state_fields"]
        if not declared:
            continue   # no declared field set -> nothing to check against
        loc = machine["node"]
        for t in machine["transitions"]:
            undeclared = _written_fields(t["value"], src) - declared
            if undeclared:
                out.append(diagnostic(
                    "HC-SM06", "error",
                    f"Transition ({t['state']}, {t['event']}) writes fields not in "
                    f"state_fields: {sorted(undeclared)}. Declare them or move the "
                    "write to a separate chain.",
                    path, line_of(loc), col_of(loc)))
    return out


SM_CHECKS = [
    check_hc_sm03_sm04,
    check_hc_sm06,
]
