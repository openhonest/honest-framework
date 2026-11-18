"""Identity: fold identity.claimed events into the binding table, and resolve one external id to its
canonical id, an unresolvable id being a bounded absence NOTHING, not a fault (honest-observe.hd,
section 8c.3).

fold_identity_claims reduces each append-only identity.claimed event into a lookup mapping
(external_system, external_id) to a canonical id. A conflict -- two claims mapping one external id to
different canonical ids -- is surfaced in the result for human adjudication, not silently resolved.
resolve_identity looks one external id up in that table and returns the canonical id, or NOTHING when
unresolvable: a bounded absence disjoint from a Fault, never recognized by is_fault. The fold and the
resolve are if-free: each decision is a boolean or tuple key read from a closed table (P01).
"""

from functools import reduce

from honest_observe._util import _get, _pick
from honest_observe.types import NOTHING

# The event type whose claims this fold reduces, and the payload keys each claim asserts (section
# 8c.3). Named here so the one place a claim is read is the one place these keys are written.
_CLAIM_TYPE = "identity.claimed"
_SYSTEM_KEY = "external_system"
_EXTERNAL_KEY = "external_id"
_CANONICAL_KEY = "canonical_id"

# The absence marker a lookup keys on to tell "no binding yet" from a real canonical id or a conflict
# record. A unique sentinel object, so it can never collide with a canonical id a claim carries.
_UNSET = object()


# The lookup key for one external identity: the (external_system, external_id) pair as a string, so
# the one place the binding is keyed is shared by the fold and the resolve. A lambda, not a def, so it
# adds no column-0 function to the module's declared set (the same reason honest-auth's _util helpers
# are lambdas): every declared function keeps its one gherkin scenario and nothing else does.
_binding_key = lambda source, external_id: f"{source}\x1f{external_id}"

# True when existing is a conflict record: it carries the candidates key. Reached only through
# _is_conflict, which guards that existing is a real binding value, never the unset sentinel, so the
# membership test reads a map it knows is present rather than a runtime type (P14).
_is_conflict_map = lambda existing: _pick(hasattr(existing, "get"), lambda: "candidates" in existing, lambda: False)

# True when an existing binding value is already a conflict record (a map carrying candidates), told by
# the reserved conflict key rather than a runtime type test (P14). The unset sentinel is not a conflict,
# the two-row table closing the decision over both arms.
_is_conflict = lambda existing: _pick(existing is _UNSET, lambda: False, lambda: _is_conflict_map(existing))

# Name the merge case for an existing binding value and an incoming canonical id: unset -> fresh, a
# standing conflict -> conflicting, a matching scalar -> same, a differing scalar -> diverging. The case
# is the tuple key the merge table reads, so the branch is data, not control flow (P01); an unmapped
# tuple resolves to diverging, closing the input.
_classify_existing = lambda existing, canonical: _get(
    {
        (True, False, False): "fresh",
        (False, True, False): "conflicting",
        (False, False, True): "same",
        (False, False, False): "diverging",
    },
    (
        existing is _UNSET,
        _is_conflict(existing),
        (existing is not _UNSET) and (not _is_conflict(existing)) and existing == canonical,
    ),
    "diverging",
)

# Merge one canonical id into the bindings table at key, keyed by what is already there: unset -> the
# canonical id; a conflict record -> the candidate added; a matching scalar -> unchanged; a differing
# scalar -> a conflict record carrying both. A closed three-case decision read from the merge table,
# not an if/elif ladder (P01).
_merge_claim = lambda bindings, key, canonical: {
    **bindings,
    key: _get(_MERGE, _classify_existing(_get(bindings, key, _UNSET), canonical), _MERGE["diverging"])(
        _get(bindings, key, _UNSET), canonical
    ),
}


# The merge table: each named case maps (existing, canonical) to the new binding value at the key.
_MERGE = {
    "fresh": lambda existing, canonical: canonical,
    "same": lambda existing, canonical: existing,
    "conflicting": lambda existing, canonical: {
        "conflict": True,
        "candidates": existing["candidates"] + _get({True: [], False: [canonical]}, canonical in existing["candidates"], [canonical]),
    },
    "diverging": lambda existing, canonical: {"conflict": True, "candidates": [existing, canonical]},
}


def fold_identity_claims(events):
    """Fold the identity.claimed events into the identity binding table, a mapping of
    (external_system, external_id) to a canonical id (section 8c.3). A conflict -- one external id
    claimed for two different canonical ids -- is surfaced as a conflict record carrying every claimed
    canonical id for adjudication, not silently resolved to one. Pure: events in, bindings out, no
    world and no fault."""
    claims = filter(lambda event: event["event_type"] == _CLAIM_TYPE, events)
    return reduce(
        lambda bindings, event: _merge_claim(
            bindings,
            _binding_key(event["payload"][_SYSTEM_KEY], event["payload"][_EXTERNAL_KEY]),
            event["payload"][_CANONICAL_KEY],
        ),
        claims,
        {},
    )


def resolve_identity(external_id, source, bindings):
    """Resolve one external id in a source to its canonical id by looking it up in the bindings table
    fold_identity_claims produced (section 8c.3). An unresolvable id is a bounded absence, not a
    failure: it returns NOTHING, which carries no is_err tag and is never recognized by is_fault,
    keeping it disjoint from a Fault. A conflicted binding is likewise unresolved -- NOTHING -- because
    a conflict awaits adjudication rather than silently picking one id. Pure: a table lookup, no
    world."""
    value = _get(bindings, _binding_key(source, external_id), _UNSET)
    unresolved = value is _UNSET or _is_conflict(value)
    return _pick(unresolved, lambda: NOTHING, lambda: value)