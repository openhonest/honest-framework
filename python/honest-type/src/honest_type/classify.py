"""classify() — the two-pass engine (section 6), edge cases (section 9), and the
fault/rejection contract (section 11).

Unit 2: base classification + flat (required) binding. Composed types and Maybe follow.

Returns a manifest (flat dict slot->value, plus `_rejections` for client/server
rejections) — or, on a server-bug fault (non-string token, throwing predicate), the
Result error shape `{"err": fault}`. Rejections are data in the manifest; faults are a
distinct return because the manifest would be a lie.
"""

from honest_type.recognizers import recognize
from honest_type.reserved import is_reserved
from honest_type.types import fault, rejection, ticket
from honest_type.vocabulary import auto_binding, is_maybe, unwrap_maybe


# The predicate-invocation boundary: calling a user-supplied predicate crosses into
# untrusted code. A throw becomes a predicate_error fault (data), never an exception in
# the pure core. This is the one place catching is legitimate (Typed Exceptions at the
# Boundary), hence the block disable.
# honest: disable HC-P002
def _safe_recognize(token, recognizer):
    """Run a recognizer; return (matched, error_message). error_message is set only when a
    predicate threw."""
    try:
        return recognize(token, recognizer), None
    except Exception as exc:
        return None, str(exc)
# honest: enable HC-P002


def _classify_token(token, vocab):
    """Pass 1 (section 6): one token -> a ticket, a rejection, or a fault."""
    matched_type = None
    for type_name, recognizer in vocab["base_types"].items():
        ok, error = _safe_recognize(token, recognizer)
        if error is not None:
            return fault(
                "predicate_error",
                f"Predicate for type '{type_name}' threw on token '{token}'",
                "server",
                {"type_name": type_name, "token": token, "exception": error},
            )
        if not ok:
            continue
        if recognizer["kind"] == "predicate" and is_reserved(token):
            return rejection(token, "reserved_word", type_name)
        matched_type = type_name
    if matched_type is None:
        return rejection(token, "unrecognized")
    return ticket(matched_type, token)


def _requirements_met(comp, ticket_index_by_type, tickets):
    """True if every (req_type, req_value) in a composed type's requires is present."""
    for required_type, required_value in comp["requires"].items():
        index = ticket_index_by_type.get(required_type)
        if index is None or tickets[index]["value"] != required_value:
            return False
    return True


def _resolve_bindings(tickets, rejections, vocab, bind):
    """Pass 2 (section 6): composition (2a), binding (2b), Maybe (2c), required (2d)."""
    manifest = {}
    out_rejections = list(rejections)
    ticket_index_by_type = {tk["type"]: i for i, tk in enumerate(tickets)}
    captured = set()
    claimed_types = set()  # capture types of a composed that fired — base binding suppressed
    composed_names = {comp["name"] for comp in vocab["composed_types"]}

    # Phase 2a — composed types: a met composition captures its token and binds it to the
    # composed slot, overriding the captured type's base binding.
    for comp in vocab["composed_types"]:
        if comp["name"] not in bind or not _requirements_met(comp, ticket_index_by_type, tickets):
            continue
        slot = unwrap_maybe(bind[comp["name"]])
        capture_type = unwrap_maybe(comp["captures"])
        capture_index = ticket_index_by_type.get(capture_type)
        if capture_index is not None:
            captured.add(capture_index)
            claimed_types.add(capture_type)
            manifest[slot] = tickets[capture_index]["value"]
        elif is_maybe(comp["captures"]):
            claimed_types.add(capture_type)
            manifest[slot] = None  # Nothing — required met but captured token absent
        # else: required capture absent -> composed does not bind; capture type falls through

    # Phase 2b — bind remaining (uncaptured) tickets to their slots.
    for index, tk in enumerate(tickets):
        if index in captured:
            continue
        type_name = tk["type"]
        if type_name not in bind:
            out_rejections.append(rejection(tk["value"], "unbound_type", type_name))
            continue
        slot = unwrap_maybe(bind[type_name])
        if slot in manifest:
            out_rejections.append(rejection(tk["value"], "duplicate_slot", slot))
            continue
        manifest[slot] = tk["value"]

    # Phase 2c — fill Nothing for unmatched maybe slots.
    for slot_or_maybe in bind.values():
        if is_maybe(slot_or_maybe) and unwrap_maybe(slot_or_maybe) not in manifest:
            manifest[unwrap_maybe(slot_or_maybe)] = None  # Nothing

    # Phase 2d — a required type with NO token provided (and not a composed name) is missing.
    # A captured base type DID have a token, so it is not "missing" even though its base slot
    # is empty.
    for type_name, slot_or_maybe in bind.items():
        if is_maybe(slot_or_maybe) or type_name in composed_names or type_name in claimed_types:
            continue
        if slot_or_maybe not in manifest and type_name not in ticket_index_by_type:
            out_rejections.append(rejection(None, "missing_required", type_name))

    if out_rejections:
        manifest["_rejections"] = out_rejections
    return manifest


def classify(tokens, vocab, bind=None):
    """Classify tokens against a vocabulary into a manifest (or {'err': fault})."""
    binding = bind if bind is not None else auto_binding(vocab)
    tickets = []
    rejections = []
    for token in tokens:
        if token is None:
            rejections.append(rejection(None, "null_token"))
            continue
        if not isinstance(token, str):  # honest: ignore HC-P005  (primitive input-contract guard, not domain dispatch)
            return {"err": fault("non_string_token", f"classify() requires string tokens. Got: {token!r}", "server", {"token": token})}
        if token == "":
            rejections.append(rejection("", "empty_token"))
            continue
        result = _classify_token(token, vocab)
        if "code" in result:        # a fault — server bug, short-circuit
            return {"err": result}
        if "reason" in result:      # a rejection
            rejections.append(result)
            continue
        tickets.append(result)      # a ticket
    return _resolve_bindings(tickets, rejections, vocab, binding)
