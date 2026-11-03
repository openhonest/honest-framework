"""honest-check construction-time rule sub-core, split from core.py for L1.17 (section 4.1)."""

import itertools
from honest_check.nodes import base_types_of, call_arguments, canonical_name, diagnostic, literal_string, predicate_is_risky, string_members


def check_construction(ctx):
    """Construction-time rules (section 4.1): HC001/HC003/HC006/HC007/HC011 and the
    HC-SM rules, dispatched by the framework constructor each call site resolves to. The
    per-rule logic nests here as data; ctx carries the parse."""
    nodes = ctx["nodes"]
    def check_vocabulary(call_node):
        """HC003 overlap, HC011 catch-all predicate, and HC006 unknown composed base
        (section 4.1)."""
        findings = []
        positionals, keywords = call_arguments(ctx, call_node)
        if not positionals or positionals[0].type != "dictionary":
            return findings
        base_types = base_types_of(ctx, positionals[0])

        for a, b in itertools.combinations(base_types, 2):
            kind_a, members_a = base_types[a]
            kind_b, members_b = base_types[b]
            if kind_a == "set" and kind_b == "set":
                overlap = members_a & members_b
                if overlap:
                    findings.append(
                        diagnostic(ctx,
                            "HC003",
                            "error",
                            f"Types {a!r} and {b!r} share values: {sorted(overlap)}",
                            call_node,
                        )
                    )
            else:
                findings.append(
                    diagnostic(ctx,
                        "HC003",
                        "info",
                        f"Types {a!r} and {b!r} may overlap on a value — "
                        "verified by honest-test",
                        call_node,
                    )
                )

        for name, (kind, payload) in base_types.items():
            if kind != "predicate":
                continue
            if payload is not None and predicate_is_risky(payload):
                findings.append(
                    diagnostic(ctx,
                        "HC009",
                        "warning",
                        f"Predicate recognizer {name!r} may throw on non-matching input. "
                        "Wrap in try/except or guard with isinstance() — verified by "
                        "honest-test.",
                        call_node,
                    )
                )
            findings.append(
                diagnostic(ctx,
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
                if child.type == "call" and canonical_name(ctx, child) == "composed":
                    findings.extend(check_composed(child, base_types))
        return findings

    def check_composed(call_node, base_types):
        """HC006: a composed type whose requires or captures names a base the vocabulary does
        not declare (section 4.1)."""
        findings = []
        positionals, _keywords = call_arguments(ctx, call_node)
        if len(positionals) < 2 or positionals[1].type != "dictionary":
            return findings
        for pair in positionals[1].named_children:
            if pair.type != "pair":
                continue
            required = literal_string(pair.child_by_field_name("key"))
            if required not in base_types:
                findings.append(
                    diagnostic(ctx,
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
                    diagnostic(ctx,
                        "HC006",
                        "error",
                        f"Composed type captures unknown base type {captured!r}",
                        call_node,
                    )
                )
        return findings

    def check_chain(call_node):
        """HC007: a chain() constructed with no links is empty (section 4.1)."""
        positionals, _keywords = call_arguments(ctx, call_node)
        if not positionals:
            return [diagnostic(ctx, "HC007", "error", "Chain has no links", call_node)]
        return []

    def check_state_machine(call_node):
        """HC-SM01/02/05: a transition state or event, or the initial state, not in its
        vocabulary; HC-SM03/04: an unreachable or dead state (section 4.1)."""
        findings = []
        positionals, keywords = call_arguments(ctx, call_node)
        if len(positionals) < 4:
            return findings
        states = string_members(ctx, positionals[0])
        state_set = set(states)
        events = set(string_members(ctx, positionals[1]))
        transitions = positionals[2]
        initial = literal_string(positionals[3]) if positionals[3].type == "string" else None
        terminal_node = keywords.get("terminal")
        if terminal_node is None and len(positionals) >= 5:
            terminal_node = positionals[4]
        terminal = set(string_members(ctx, terminal_node)) if terminal_node is not None else set()

        transition_pairs = []
        for pair in transitions.named_children:
            if pair.type != "pair":
                continue
            key = pair.child_by_field_name("key")
            if key.type != "tuple":
                continue
            members = string_members(ctx, key)
            if len(members) < 2:
                continue
            state, event = members[0], members[1]
            value = pair.child_by_field_name("value")
            target = literal_string(value) if value is not None and value.type == "string" else None
            transition_pairs.append((state, event, target))
            if state not in state_set:
                findings.append(
                    diagnostic(ctx,
                        "HC-SM01",
                        "error",
                        f"State {state!r} in transition table not in states vocabulary",
                        call_node,
                    )
                )
            if event not in events:
                findings.append(
                    diagnostic(ctx,
                        "HC-SM02",
                        "error",
                        f"Event {event!r} in transition table not in events vocabulary",
                        call_node,
                    )
                )
        if initial is not None and initial not in state_set:
            findings.append(
                diagnostic(ctx,
                    "HC-SM05",
                    "error",
                    f"Initial state {initial!r} not in states vocabulary",
                    call_node,
                )
            )

        # HC-SM03: a declared state the forward walk from the initial state never reaches,
        # and that is not itself the initial state, is unreachable. The walk is a plain set
        # closure over the transition edges.
        if initial is not None:
            reachable = {initial}
            frontier = {initial}
            while frontier:
                nxt = set()
                for state, _event, target in transition_pairs:
                    if state in frontier and target is not None and target not in reachable:
                        reachable.add(target)
                        nxt.add(target)
                frontier = nxt
            for state in states:
                if state not in reachable and state != initial:
                    findings.append(
                        diagnostic(ctx,
                            "HC-SM03",
                            "warning",
                            f"State {state!r} is unreachable",
                            call_node,
                        )
                    )

        # HC-SM04: a declared state with no outgoing transition that is not declared terminal
        # is a dead state.
        states_with_outgoing = {state for state, _event, _target in transition_pairs}
        for state in states:
            if state not in states_with_outgoing and state not in terminal:
                findings.append(
                    diagnostic(ctx,
                        "HC-SM04",
                        "warning",
                        f"State {state!r} has no outgoing transitions and is not "
                        "declared terminal",
                        call_node,
                    )
                )
        return findings
    construction_handlers = {
        "vocabulary": check_vocabulary,
        "chain": check_chain,
        "state_machine": check_state_machine,
    }
    diagnostics = []
    for node in nodes:
        if node.type != "call":
            continue
        canonical = canonical_name(ctx, node)
        if canonical not in construction_handlers:
            continue
        diagnostics.extend(construction_handlers[canonical](node))
    return diagnostics
