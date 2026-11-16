"""classify() — the two-pass engine (section 6), edge cases (section 9), and the
fault/rejection contract (section 11).

Unit 2: base classification + flat (required) binding. Composed types and Maybe follow.

Returns a manifest (flat dict slot->value, plus `_rejections` for client/server
rejections) — or, on a server-bug fault (non-string token, throwing predicate), the
Result error shape `{"err": fault}`. Rejections are data in the manifest; faults are a
distinct return because the manifest would be a lie.
"""

from functools import reduce

from honest_type._util import _pick, _read_or
from honest_type.recognizers import recognize
from honest_type.reserved import is_reserved
from honest_type.types import fault, rejection, ticket
from honest_type.vocabulary import auto_binding, is_maybe, unwrap_maybe


# The predicate-invocation boundary: calling a user-supplied predicate crosses into
# untrusted code. A throw becomes a predicate_error fault (data), never an exception in
# the pure core. This is the one place catching is legitimate (Typed Exceptions at the
# Boundary), so the try carries an inline HC-P002 ignore naming why.
def _safe_recognize(token, recognizer):
    """Run a recognizer; return (matched, error_message). error_message is set only when a
    predicate threw."""
    try:  # honest: ignore HC-P002: running a user-supplied predicate is the classification boundary; a throw becomes a fault value, not a raise (section 9.6)
        return recognize(token, recognizer), None
    except Exception as exc:
        return None, str(exc)


def _pass_one_hit(matched_type, type_name, recognizer, token) -> dict:
    """A token matched type_name: stop with a reserved-word rejection when a predicate matched a
    reserved word, stop with a vocabulary_overlap fault when a type was already matched, else
    record this as the first match. Returns the next pass-1 scan state."""
    return _pick(
        recognizer["kind"] == "predicate" and is_reserved(token),
        lambda: {"done": rejection(token, "reserved_word", type_name)},
        lambda: _pick(
            matched_type is not None,
            lambda: {"done": fault(
                "vocabulary_overlap",
                f"Token '{token}' matches both '{matched_type}' and '{type_name}'",
                "server", [], {"token": token, "types": [matched_type, type_name]},
            )},
            lambda: {"matched": type_name},
        ),
    )


def _pass_one_type(matched_type, type_recognizer, token) -> dict:
    """Scan one (type_name, recognizer) against the token: a predicate throw stops with a
    predicate_error fault; a non-match leaves the running match unchanged; a match hands off to
    _pass_one_hit. Returns the next pass-1 scan state."""
    type_name, recognizer = type_recognizer
    matched, error = _safe_recognize(token, recognizer)
    return _pick(
        error is not None,
        lambda: {"done": fault(
            "predicate_error",
            f"Predicate for type '{type_name}' threw on token '{token}'",
            "server", [], {"type_name": type_name, "token": token, "exception": error},
        )},
        lambda: _pick(
            not matched,
            lambda: {"matched": matched_type},
            lambda: _pass_one_hit(matched_type, type_name, recognizer, token),
        ),
    )


def _pass_one_step(state, type_recognizer, token) -> dict:
    """One fold step over the vocabulary's base types: pass a stopped scan through untouched, else
    scan this type. The stopped arm never runs the recognizer."""
    return _pick(
        "done" in state,
        lambda: state,
        lambda: _pass_one_type(state["matched"], type_recognizer, token),
    )


def _pass_one_outcome(matched_type, token):
    """The result of a finished pass-1 scan that never stopped: a ticket for the single matched
    type, or an unrecognized rejection when nothing matched."""
    return _pick(
        matched_type is None,
        lambda: rejection(token, "unrecognized"),
        lambda: ticket(matched_type, token),
    )


def _classify_token(token, vocab):
    """Pass 1 (section 6): one token -> a ticket, a rejection, or a fault."""
    final = reduce(
        lambda state, type_recognizer: _pass_one_step(state, type_recognizer, token),
        vocab["base_types"].items(),
        {"matched": None},
    )
    return _pick(
        "done" in final,
        lambda: final["done"],
        lambda: _pass_one_outcome(final["matched"], token),
    )


def _requirement_met(comp_requirement, ticket_index_by_type, tickets) -> bool:
    """True if one (req_type, req_value) of a composed type's requires is present with that value."""
    required_type, required_value = comp_requirement
    index = _read_or(ticket_index_by_type, required_type, None)
    return _pick(
        index is None,
        lambda: False,
        lambda: tickets[index]["value"] == required_value,
    )


def _requirements_met(comp, ticket_index_by_type, tickets):
    """True if every (req_type, req_value) in a composed type's requires is present."""
    return all(
        _requirement_met(item, ticket_index_by_type, tickets)
        for item in comp["requires"].items()
    )


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
    firing = filter(
        lambda comp: comp["name"] in bind and _requirements_met(comp, ticket_index_by_type, tickets),
        vocab["composed_types"],
    )
    for comp in firing:
        slot = unwrap_maybe(bind[comp["name"]])
        capture_type = unwrap_maybe(comp["captures"])
        capture_index = _read_or(ticket_index_by_type, capture_type, None)
        _pick(
            capture_index is not None,
            lambda: (captured.add(capture_index), claimed_types.add(capture_type),
                     manifest.update({slot: tickets[capture_index]["value"]})),
            lambda: _pick(
                is_maybe(comp["captures"]),
                lambda: (claimed_types.add(capture_type), manifest.update({slot: None})),
                lambda: None,
            ),
        )

    # Phase 2b — bind remaining (uncaptured) tickets to their slots.
    uncaptured = filter(lambda index_tk: index_tk[0] not in captured, enumerate(tickets))
    for index, tk in uncaptured:
        type_name = tk["type"]
        _pick(
            type_name not in bind,
            lambda: out_rejections.append(rejection(tk["value"], "unbound_type", type_name)),
            lambda: _pick(
                unwrap_maybe(bind[type_name]) in manifest,
                lambda: out_rejections.append(rejection(tk["value"], "duplicate_slot", unwrap_maybe(bind[type_name]))),
                lambda: manifest.update({unwrap_maybe(bind[type_name]): tk["value"]}),
            ),
        )

    # Phase 2c — fill Nothing for unmatched maybe slots.
    unmatched_maybe = filter(
        lambda slot_or_maybe: is_maybe(slot_or_maybe) and unwrap_maybe(slot_or_maybe) not in manifest,
        bind.values(),
    )
    for slot_or_maybe in unmatched_maybe:
        manifest[unwrap_maybe(slot_or_maybe)] = None  # Nothing

    # Phase 2d — a required type with NO token provided (and not a composed name) is missing.
    # A captured base type DID have a token, so it is not "missing" even though its base slot
    # is empty.
    missing = filter(
        lambda item: (not is_maybe(item[1]) and item[0] not in composed_names and item[0] not in claimed_types)
        and (item[1] not in manifest and item[0] not in ticket_index_by_type),
        bind.items(),
    )
    for type_name, slot_or_maybe in missing:
        out_rejections.append(rejection(None, "missing_required", type_name))

    _pick(bool(out_rejections), lambda: manifest.update({"_rejections": out_rejections}), lambda: None)
    return manifest


def _non_string_fault(token):
    """The server fault a non-string token raises at the boundary (section 9.5). The received type
    is read only to name it in the message and detail — nothing branches on it — so a fault that
    must report the type it got can read one without violating HC-P005."""
    received_type = type(token).__name__  # honest: ignore HC-P005: section 9.5 requires the received type
    return fault("non_string_token",
                 f"classify() requires string tokens. Got: {received_type} {token!r}",
                 "server", [], {"token": token, "received_type": received_type})


def _append_rejection(state, rej):
    """Record a rejection in the running scan state and return it."""
    state["rejections"].append(rej)
    return state


def _append_ticket(state, tk):
    """Record a ticket in the running scan state and return it."""
    state["tickets"].append(tk)
    return state


def _scan_classified(state, result):
    """Route pass-1's result: a fault (has code) stops the scan; a rejection (has reason) is
    recorded; anything else is a ticket. Returns the next scan state."""
    return _pick(
        "code" in result,
        lambda: {"err": result},
        lambda: _pick(
            "reason" in result,
            lambda: _append_rejection(state, result),
            lambda: _append_ticket(state, result),
        ),
    )


def _scan_token(state, token, vocab):
    """Classify one token into the running scan state: a null token and an empty token are
    rejections, a non-string token stops with a server fault, anything else runs pass 1."""
    return _pick(
        token is None,
        lambda: _append_rejection(state, rejection(None, "null_token")),
        lambda: _pick(
            not isinstance(token, str),  # honest: ignore HC-P005: primitive input-contract guard, not domain dispatch
            lambda: {"err": _non_string_fault(token)},
            lambda: _pick(
                token == "",
                lambda: _append_rejection(state, rejection("", "empty_token")),
                lambda: _scan_classified(state, _classify_token(token, vocab)),
            ),
        ),
    )


def _scan_step(state, token, vocab):
    """One fold step over the tokens: pass a stopped scan (a server fault) through untouched, else
    classify this token."""
    return _pick(
        "err" in state,
        lambda: state,
        lambda: _scan_token(state, token, vocab),
    )


def classify(tokens, vocab, bind=None):
    """Classify tokens against a vocabulary into a manifest (or {'err': fault})."""
    binding = _pick(bind is not None, lambda: bind, lambda: auto_binding(vocab))
    final = reduce(
        lambda state, token: _scan_step(state, token, vocab),
        tokens,
        {"tickets": [], "rejections": []},
    )
    return _pick(
        "err" in final,
        lambda: {"err": final["err"]},
        lambda: _resolve_bindings(final["tickets"], final["rejections"], vocab, binding),
    )
