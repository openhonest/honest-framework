"""The two-pass classify() algorithm (spec §6) and edge-case rules (§9).

Pass 1 (`classify_token`): each token -> ticket or rejection (or a fault for
the two server-bug conditions: predicate_error, non_string_token).
Pass 2 (`resolve_bindings`): 2a composed-type resolution, 2b base binding,
2c maybe-fill, 2d required-binding check.

Two passes guarantee order-independence: composed types see the whole input,
not just tokens seen so far.

classify() returns a manifest (a flat dict, with an optional "_rejections"
list) on success, or a bare fault for the two server-bug conditions.
"""
from __future__ import annotations

from honest_type.binding import auto_binding
from honest_type.reserved import is_reserved
from honest_type.result import fault, is_fault
from honest_type.types import (
    Nothing,
    Recognizer,
    is_maybe,
    rejection,
    ticket,
    unwrap_maybe,
)


# --- Recognizer matching: dict-dispatch on kind, no isinstance ladder ----

_MATCHERS = {
    "set":         lambda rec, tok: tok in rec["members"],
    "insensitive": lambda rec, tok: tok.lower() in rec["members"],
    "predicate":   lambda rec, tok: bool(rec["fn"](tok)),
}


def _matches(recognizer: Recognizer, token: str) -> bool:
    return _MATCHERS[recognizer["kind"]](recognizer, token)


# --- Pass 1 --------------------------------------------------------------


def classify_token(token: str, vocabulary: dict):
    """Classify one token against the base types. Returns a ticket, a
    rejection, or a (predicate_error) fault."""
    matched_type = None
    for type_name, recognizer in vocabulary["base_types"].items():
        try:
            matched = _matches(recognizer, token)
        except Exception as exc:                       # spec §9.6
            return fault(
                "predicate_error",
                f"Predicate for type {type_name!r} threw on token {token!r}",
                category="server",
                detail={"type_name": type_name, "token": token, "exception": str(exc)},
            )
        if not matched:
            continue
        if recognizer["kind"] == "predicate" and is_reserved(token):   # spec §2
            return rejection(token, "reserved_word")
        if matched_type is not None:                   # should be caught at construction
            return fault(
                "vocabulary_overlap",
                f"token {token!r} matches both {matched_type!r} and {type_name!r}",
                category="server",
            )
        matched_type = type_name

    if matched_type is None:
        return rejection(token, "unrecognized")        # spec §6 / §11.3
    return ticket(matched_type, token)


def _is_rejection(item) -> bool:
    return isinstance(item, dict) and "reason" in item


# --- Pass 2 --------------------------------------------------------------


def resolve_bindings(tickets: list, vocabulary: dict, binding: dict) -> dict:
    manifest: dict = {}
    rejections: list = []
    captured_ids: set = set()

    ticket_by_type: dict = {}
    for item in tickets:
        if _is_rejection(item):
            continue
        ticket_by_type[item["type"]] = item

    # --- Phase 2a: resolve composed types ---
    for comp in vocabulary["composed_types"]:
        if comp["name"] not in binding:
            continue
        requirements_met = True
        for req_type, req_value in comp["requires"].items():
            present = ticket_by_type.get(req_type)
            if present is None or present["value"] != req_value:
                requirements_met = False
                break
        if not requirements_met:
            continue

        capture = comp["captures"]
        capture_type = unwrap_maybe(capture)
        slot = unwrap_maybe(binding[comp["name"]])
        captured_ticket = ticket_by_type.get(capture_type)
        if captured_ticket is not None:
            captured_ids.add(id(captured_ticket))
            manifest[slot] = captured_ticket["value"]
        elif is_maybe(capture):
            manifest[slot] = Nothing
        # else: required capture absent -> composed type does not match

    # --- Phase 2b: bind remaining (uncaptured) tickets ---
    for item in tickets:
        if _is_rejection(item):
            rejections.append(item)
            continue
        if id(item) in captured_ids:
            continue
        if item["type"] in binding:
            slot = unwrap_maybe(binding[item["type"]])
            if slot in manifest:
                rejections.append(rejection(item["value"], "duplicate_slot", slot))
                continue
            manifest[slot] = item["value"]
        else:
            rejections.append(rejection(item["value"], "unbound_type", item["type"]))

    # --- Phase 2c: fill Nothing for unmatched maybe bindings ---
    for type_name, slot_or_maybe in binding.items():
        if is_maybe(slot_or_maybe):
            slot = unwrap_maybe(slot_or_maybe)
            if slot not in manifest:
                manifest[slot] = Nothing

    # --- Phase 2d: required bindings ---
    # missing_required means the type had NO classified ticket (spec §5.3),
    # not merely that its slot is absent: a required base type whose token was
    # captured by a composed type (its base slot suppressed) is still
    # satisfied. The §6 pseudocode's "slot NOT IN manifest" is imprecise here;
    # the §5.3 prose and the §6 worked example govern.
    composed_names = {c["name"] for c in vocabulary["composed_types"]}
    for type_name, slot_or_maybe in binding.items():
        if not is_maybe(slot_or_maybe):
            if type_name not in ticket_by_type and type_name not in composed_names:
                rejections.append(rejection(None, "missing_required", type_name))

    if rejections:
        manifest["_rejections"] = rejections
    return manifest


# --- Orchestrator + edge cases (spec §9) ---------------------------------


def classify(tokens: list, vocabulary: dict, binding: dict | None = None):
    if binding is None:
        binding = auto_binding(vocabulary)

    tickets: list = []
    for token in tokens:
        if token is None:                              # spec §9.4
            tickets.append(rejection(None, "null_token"))
            continue
        if not isinstance(token, str):                 # spec §9.5 — server fault
            return fault(
                "non_string_token",
                f"classify() requires string tokens. Got: {type(token).__name__} {token!r}",
                category="server",
                detail={"token": token, "received_type": type(token).__name__},
            )
        if token == "":                                # spec §9.3
            tickets.append(rejection("", "empty_token"))
            continue
        result = classify_token(token, vocabulary)
        if is_fault(result):                           # predicate_error / overlap short-circuit
            return result
        tickets.append(result)

    return resolve_bindings(tickets, vocabulary, binding)
