"""honest-type rules: vocabulary, chain, binding and state-machine checks (section 4.1).

The framework-tier rules that make a vocabulary the type system: overlapping types,
unbound base types, chain type-flow, state-machine reachability, and the persist/http
binding rules that ride on the same declaration graph.
"""

from itertools import combinations
from honest_check.declgraph import (
    assigned_name,
    build_vocabulary_definitions,
    call_location,
    constructor_calls,
    defined_function_names,
    extract_bindings,
    extract_chains,
    extract_composed_types,
    extract_links,
    extract_state_machines,
    extract_vocabularies,
    function_name,
    keyword_args,
    link_decorator_call,
    positional_arg_count,
    resolve_aliases,
    vocab_binding_pairings,
    vocab_expr_type_names,
    vocabulary_base_types,
)
from honest_check.diagnostics import (
    Diagnostic,
    diagnostic,
)
from honest_check.watchlists import (
    IO_WATCH_LIST,
    NONDETERMINISTIC_WATCH_LIST,
    matches_watchlist,
)
from honest_parse import (
    line_col,
    node_text,
    walk,
)
from honest_check._rule_helpers import (
    _HTTP_RESPONSE_MARKERS,
    _ROUTING_KEYS,
    _call_name,
    _produced_slot_keys,
    _qualified_call_name,
    _reachable_states,
    _recognizer_identity,
    _risky_predicate_ops,
)


def check_hc007(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC007 — a chain() with no links cannot be tested (error, section 4.1)."""
    aliases = resolve_aliases(root, source)
    out: list[Diagnostic] = []
    for call in constructor_calls(root, source, aliases, "chain"):
        if positional_arg_count(call) != 0:
            continue
        line, col = call_location(call)
        name = assigned_name(call, source) or "<anonymous>"
        out.append(diagnostic("HC007", "error", path, line, col, f"Chain '{name}' has no links. Add at least one @link to the chain, or remove the chain."))
    return out


def check_hc003(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC003 — two types in one vocabulary match the same token (section 4.1).

    Set x Set overlap is decidable here (error). Predicate x Predicate cannot be
    decided statically, so an info points to honest-test. Set x Predicate (needs
    evaluating the predicate over the Set) is deferred to honest-test.
    """
    aliases = resolve_aliases(root, source)
    out: list[Diagnostic] = []
    for call in constructor_calls(root, source, aliases, "vocabulary"):
        line, col = call_location(call)
        for (name_a, rec_a), (name_b, rec_b) in combinations(
            sorted(vocabulary_base_types(call, source).items()), 2
        ):
            if rec_a[0] == "set" and rec_b[0] == "set":
                overlap = rec_a[1] & rec_b[1]
                if overlap:
                    out.append(
                        diagnostic(
                            "HC003",
                            "error",
                            path,
                            line,
                            col,
                            f"Types '{name_a}' and '{name_b}' share values: {sorted(overlap)}. Make their value sets disjoint, or merge the types.",
                        )
                    )
            if rec_a[0] == "predicate" and rec_b[0] == "predicate":
                out.append(
                    diagnostic(
                        "HC003",
                        "info",
                        path,
                        line,
                        col,
                        f"Predicate types '{name_a}' and '{name_b}' may overlap — "
                        "cannot be checked statically; verified by honest-test.",
                    )
                )
            if {rec_a[0], rec_b[0]} == {"set", "predicate"}:
                out.append(
                    diagnostic(
                        "HC003",
                        "info",
                        path,
                        line,
                        col,
                        f"Set type and predicate type ('{name_a}', '{name_b}') may overlap on a Set "
                        "value — the predicate is not evaluated here; verified by honest-test.",
                    )
                )
    return out


def check_state_machine_vocab(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-SM01/02/05 — transition or initial state/event not in its vocabulary (section 4.1)."""
    aliases = resolve_aliases(root, source)
    out: list[Diagnostic] = []
    for machine in extract_state_machines(root, source, aliases):
        line, col = machine["location"]
        if machine["states"]:
            for state, _event, _next in machine["transitions"]:
                if state not in machine["states"]:
                    out.append(diagnostic("HC-SM01", "error", path, line, col,
                        f"State '{state}' in transition table not in states vocabulary. Add it to the states vocabulary, or correct the name in the transition."))
            initial = machine["initial"]
            if initial is not None and initial not in machine["states"]:
                out.append(diagnostic("HC-SM05", "error", path, line, col,
                    f"Initial state '{initial}' not in states vocabulary. Add it to the states vocabulary, or correct the initial-state name."))
        if machine["events"]:
            for _state, event, _next in machine["transitions"]:
                if event not in machine["events"]:
                    out.append(diagnostic("HC-SM02", "error", path, line, col,
                        f"Event '{event}' in transition table not in events vocabulary. Add it to the events vocabulary, or correct the name in the transition."))
    return out


def check_state_machine_reachability(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-SM03/04 — unreachable states and dead non-terminal states (section 4.2)."""
    aliases = resolve_aliases(root, source)
    out: list[Diagnostic] = []
    for machine in extract_state_machines(root, source, aliases):
        if not machine["states"] or machine["initial"] is None:
            continue
        line, col = machine["location"]
        transitions = machine["transitions"]
        reachable = _reachable_states(machine["initial"], transitions)
        for state in sorted(machine["states"]):
            if state not in reachable and state != machine["initial"]:
                out.append(diagnostic("HC-SM03", "warning", path, line, col,
                    f"State '{state}' is unreachable. Add a transition that reaches it, or remove the state."))
        for state in sorted(machine["states"]):
            has_outgoing = any(src == state for src, _event, _target in transitions)
            if not has_outgoing and state not in machine["terminal"]:
                out.append(diagnostic("HC-SM04", "warning", path, line, col,
                    f"State '{state}' has no outgoing transitions and is not declared terminal. Add a transition out of it, or declare it a terminal state."))
    return out


def check_hc010(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC010 — a link declares emission of a type its body never produces (warning)."""
    aliases = resolve_aliases(root, source)
    vocab_defs = build_vocabulary_definitions(root, source, aliases)
    bindings = extract_bindings(root, source, aliases)
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "function_definition":
            continue
        decorator = link_decorator_call(node, source, aliases)
        if decorator is None:
            continue
        kw = keyword_args(decorator, source)
        if "emits" not in kw:
            continue
        emits = vocab_expr_type_names(kw["emits"], source, vocab_defs)
        accepts = vocab_expr_type_names(kw.get("accepts"), source, vocab_defs)
        new_emits = emits - accepts
        if not new_emits:
            continue
        binds = kw.get("binds")
        if binds is None or binds.type != "identifier" or node_text(binds, source) not in bindings:
            continue  # cannot reverse-map slot->type without the paired binding
        reverse = {slot: type_name for type_name, slot in bindings[node_text(binds, source)]["table"].items()}
        produced = {reverse[key] for key in _produced_slot_keys(node, source) if key in reverse}
        phantom = new_emits - produced
        if not phantom:
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC010",
                "warning",
                path,
                line,
                col,
                f"Link '{function_name(node, source)}' declares emission of types never "
                f"produced: {sorted(phantom)}. Remove them from the link's emits, or produce them in the body.",
            )
        )
    return out


def check_hc004(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC004 — a base type is defined in a vocabulary but never bound or composed (warning)."""
    aliases = resolve_aliases(root, source)
    vocabularies = extract_vocabularies(root, source, aliases)
    bindings = extract_bindings(root, source, aliases)
    out: list[Diagnostic] = []
    seen: set = set()
    for vocab_var, binding_var in vocab_binding_pairings(root, source, aliases):
        if vocab_var not in vocabularies or binding_var not in bindings:
            continue
        vocab = vocabularies[vocab_var]
        table = bindings[binding_var]["table"]
        line, col = vocab["location"]
        for type_name in vocab["base"]:
            in_binding = type_name in table
            in_composed = any(
                type_name in record["requires"] or type_name == record["captures"]
                for record in vocab["composed"]
            )
            if in_binding or in_composed:
                continue
            key = (vocab_var, binding_var, type_name)
            if key in seen:
                continue
            seen.add(key)
            out.append(diagnostic("HC004", "warning", path, line, col,
                f"Type '{type_name}' defined in vocabulary '{vocab_var}' but never bound or composed. Bind it in a binding table or compose it into another type, or remove it from the vocabulary."))
    return out


def check_hc005(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC005 — a binding entry names a type that is not in the paired vocabulary (warning)."""
    aliases = resolve_aliases(root, source)
    vocabularies = extract_vocabularies(root, source, aliases)
    bindings = extract_bindings(root, source, aliases)
    out: list[Diagnostic] = []
    seen: set = set()
    for vocab_var, binding_var in vocab_binding_pairings(root, source, aliases):
        if vocab_var not in vocabularies or binding_var not in bindings:
            continue
        vocab = vocabularies[vocab_var]
        binding = bindings[binding_var]
        valid = set(vocab["base"].keys()) | vocab["composed_names"]
        line, col = binding["location"]
        for type_name in binding["table"]:
            if type_name in valid:
                continue
            key = (vocab_var, binding_var, type_name)
            if key in seen:
                continue
            seen.add(key)
            out.append(diagnostic("HC005", "warning", path, line, col,
                f"Binding '{binding_var}' references type '{type_name}' not found in "
                f"vocabulary '{vocab_var}'. Add the type to the vocabulary, or correct the name in the binding."))
    return out


def check_hc_p013(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P013 — a database routing key (db_id/tenant_id/credential) is bound to a predicate
    recognizer rather than a bounded Set, so an arbitrary identifier can reach the pool layer."""
    aliases = resolve_aliases(root, source)
    vocabularies = extract_vocabularies(root, source, aliases)
    bindings = extract_bindings(root, source, aliases)
    out: list[Diagnostic] = []
    seen: set = set()
    for vocab_var, binding_var in vocab_binding_pairings(root, source, aliases):
        if vocab_var not in vocabularies or binding_var not in bindings:
            continue
        vocab = vocabularies[vocab_var]
        binding = bindings[binding_var]
        line, col = binding["location"]
        for type_name, slot in binding["table"].items():
            if slot not in _ROUTING_KEYS:
                continue
            recognizer = vocab["base"].get(type_name)
            if recognizer is None or recognizer[0] != "predicate":
                continue
            key = (vocab_var, binding_var, type_name, slot)
            if key in seen:
                continue
            seen.add(key)
            out.append(diagnostic("HC-P013", "error", path, line, col,
                f"Routing key '{slot}' is bound to predicate recognizer '{type_name}'. A database "
                "routing key must be a bounded Set recognizer: the vocabulary is the whitelist, and "
                "a predicate lets an arbitrary database identifier reach the pool layer."))
    return out


def check_hc_p014(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P014 — one recognizer is shared by types bound to different slots (field-swap risk)."""
    aliases = resolve_aliases(root, source)
    vocabularies = extract_vocabularies(root, source, aliases)
    bindings = extract_bindings(root, source, aliases)
    out: list[Diagnostic] = []
    seen: set = set()
    for vocab_var, binding_var in vocab_binding_pairings(root, source, aliases):
        if vocab_var not in vocabularies or binding_var not in bindings:
            continue
        vocab = vocabularies[vocab_var]
        table = bindings[binding_var]["table"]
        line, col = vocab["location"]
        recognizer_to_types: dict = {}
        for type_name, recognizer in vocab["base"].items():
            identity = _recognizer_identity(recognizer)
            if identity is None:
                continue
            recognizer_to_types.setdefault(identity, []).append(type_name)
        for identity, type_names in recognizer_to_types.items():
            if len(type_names) < 2:
                continue
            slots = sorted({table[name] for name in type_names if name in table})
            if len(slots) < 2:
                continue
            key = (vocab_var, binding_var, tuple(sorted(type_names)))
            if key in seen:
                continue
            seen.add(key)
            out.append(diagnostic("HC-P014", "error", path, line, col,
                f"One recognizer is shared by types {sorted(type_names)} bound to distinct "
                f"slots {slots}. Give each slot a semantically distinct recognizer, or the "
                "chain contract cannot catch a swap between them."))
    return out


def check_hc008(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC008 — a non-boundary @link performs I/O or non-deterministic work (warning).

    The framework-tier companion to HC-P004: links are the I/O-adjacent layer, so an
    impure link gets a warning nudging boundary=True. HC-P004 still raises the
    principle-tier error on the offending call.
    """
    aliases = resolve_aliases(root, source)
    io = IO_WATCH_LIST["python"]
    nondeterministic = NONDETERMINISTIC_WATCH_LIST["python"]
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "function_definition":
            continue
        decorator = link_decorator_call(node, source, aliases)
        if decorator is None:
            continue
        kw = keyword_args(decorator, source)
        if "boundary" in kw and node_text(kw["boundary"], source) == "True":
            continue
        body = node.child_by_field_name("body")
        hits = sorted(
            {
                name
                for sub in walk(body)
                if sub.type == "call"
                for name in [_qualified_call_name(sub, source)]
                if matches_watchlist(name, io) or matches_watchlist(name, nondeterministic)
            }
        )
        if not hits:
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC008",
                "warning",
                path,
                line,
                col,
                f"Link '{function_name(node, source)}' may be impure: {hits}. "
                "Add boundary=True if the I/O is intentional.",
            )
        )
    return out


def check_hc_p017(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-P017 — function produces HTTP output but is not a @link with emits (error)."""
    aliases = resolve_aliases(root, source)
    out: list[Diagnostic] = []
    for node in walk(root):
        if node.type != "function_definition":
            continue
        body = node.child_by_field_name("body")
        marker = None
        for sub in walk(body):
            if sub.type == "call" and _call_name(sub, source) in _HTTP_RESPONSE_MARKERS:
                marker = _call_name(sub, source)
                break
        if marker is None:
            continue
        decorator = link_decorator_call(node, source, aliases)
        if decorator is not None and "emits" in keyword_args(decorator, source):
            continue
        line, col = line_col(node)
        out.append(
            diagnostic(
                "HC-P017",
                "error",
                path,
                line,
                col,
                f"Function '{function_name(node, source)}' produces HTTP output "
                f"('{marker}') without being a declared @link with emits vocabulary. "
                "Declare emits covering status, content-type, and body shape, or "
                "delegate to a serializer link.",
            )
        )
    return out


def check_hc001(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC001 — a function used in a chain has no @link vocabulary declared (error)."""
    aliases = resolve_aliases(root, source)
    vocab_defs = build_vocabulary_definitions(root, source, aliases)
    links = extract_links(root, source, aliases, vocab_defs)
    defined = defined_function_names(root, source)
    out: list[Diagnostic] = []
    for chain in extract_chains(root, source, aliases):
        line, col = chain["location"]
        for link_name in chain["links"]:
            if link_name in links or link_name not in defined:
                # A link, or an external/chain reference we cannot judge — skip.
                continue
            out.append(
                diagnostic(
                    "HC001",
                    "error",
                    path,
                    line,
                    col,
                    f"Function '{link_name}' in chain has no vocabulary declared. "
                    "Wrap with @link(accepts=..., emits=...).",
                )
            )
    return out


def check_hc002(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC002 — a link accepts types its predecessor does not emit (error)."""
    aliases = resolve_aliases(root, source)
    vocab_defs = build_vocabulary_definitions(root, source, aliases)
    links = extract_links(root, source, aliases, vocab_defs)
    out: list[Diagnostic] = []
    for chain in extract_chains(root, source, aliases):
        line, col = chain["location"]
        sequence = chain["links"]
        for index in range(1, len(sequence)):
            previous = links.get(sequence[index - 1])
            current = links.get(sequence[index])
            if previous is None or current is None:
                continue
            emits = previous["emits"]
            accepts = current["accepts"]
            if not emits or not accepts:
                continue
            missing = accepts - emits
            if missing:
                out.append(
                    diagnostic(
                        "HC002",
                        "error",
                        path,
                        line,
                        col,
                        f"Link '{sequence[index]}' accepts types not provided by previous "
                        f"link '{sequence[index - 1]}': {sorted(missing)}. Emit those types from the previous link, or drop them from this link's accepts.",
                    )
                )
    return out


def check_hc006(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC006 — a composed type's requires/captures names a base type not in the vocabulary."""
    aliases = resolve_aliases(root, source)
    out: list[Diagnostic] = []
    for call in constructor_calls(root, source, aliases, "vocabulary"):
        base_names = set(vocabulary_base_types(call, source).keys())
        for composed in extract_composed_types(call, source, aliases):
            line, col = composed["location"]
            for required in sorted(composed["requires"]):
                if required not in base_names:
                    out.append(diagnostic("HC006", "error", path, line, col,
                        f"Composed type '{composed['name']}' requires unknown base type '{required}'. Declare the base type in the vocabulary, or correct its name."))
            captures = composed["captures"]
            if captures is not None and captures not in base_names:
                out.append(diagnostic("HC006", "error", path, line, col,
                    f"Composed type '{composed['name']}' captures unknown base type '{captures}'. Declare the base type in the vocabulary, or correct its name."))
    return out


def check_hc009(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC009 — a predicate may throw on non-matching input (warning)."""
    aliases = resolve_aliases(root, source)
    out: list[Diagnostic] = []
    for call in constructor_calls(root, source, aliases, "vocabulary"):
        for type_name, recognizer in vocabulary_base_types(call, source).items():
            if recognizer[0] != "predicate":
                continue
            risky = _risky_predicate_ops(recognizer[1], source)
            if not risky:
                continue
            line, col = line_col(recognizer[1])
            out.append(
                diagnostic(
                    "HC009",
                    "warning",
                    path,
                    line,
                    col,
                    f"Predicate '{type_name}' may throw on non-matching input: "
                    f"{sorted(risky)}. Guard the access or wrap in try/except.",
                )
            )
    return out


def check_hc011(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC011 — catch-all recognizer. Sets are bounded; predicates defer to honest-test.

    A Set recognizer is bounded by construction and can never be a catch-all, so it
    is clean. Detecting a catch-all predicate requires sampling the predicate
    (section 4.1) — that is a runtime check, so honest-check emits an info routing
    it to honest-test (section 4.3) rather than evaluating arbitrary code.
    """
    aliases = resolve_aliases(root, source)
    out: list[Diagnostic] = []
    for call in constructor_calls(root, source, aliases, "vocabulary"):
        for type_name, recognizer in vocabulary_base_types(call, source).items():
            if recognizer[0] != "predicate":
                continue
            line, col = line_col(recognizer[1])
            out.append(
                diagnostic(
                    "HC011",
                    "info",
                    path,
                    line,
                    col,
                    f"Catch-all check for predicate type '{type_name}' requires sampling "
                    "and is verified by honest-test.",
                )
            )
    return out
