"""Vocabulary construction, overlap detection, and merge (spec §2, §3).

`vocabulary()` returns a Result: ok(Vocabulary) or err(fault). Construction
fails as data — never an exception — for a reserved-word Set member
(§2 / §14.5) or a Set-vs-Set overlap (§3). Predicate overlaps and
predicate reserved-word matches are not decidable here; they are caught at
classify() time or by honest-test.
"""
from __future__ import annotations

from honest_type.reserved import reservation_layer
from honest_type.result import err, fault, ok
from honest_type.types import (
    ComposedType,
    Recognizer,
    Vocabulary,
    set_recognizer,
)


def _coerce_recognizer(value) -> Recognizer:
    """Accept a tagged recognizer, a raw set/frozenset (-> set recognizer), or
    a callable (-> predicate recognizer)."""
    if isinstance(value, dict) and "kind" in value:
        return value
    if isinstance(value, (set, frozenset)):
        return set_recognizer(value)
    if callable(value):
        return {"kind": "predicate", "fn": value}
    raise TypeError(f"not a recognizer: {value!r}")


def _set_members(recognizer: Recognizer):
    """Members of a Set/insensitive recognizer, or None for predicates."""
    if recognizer["kind"] in ("set", "insensitive"):
        return recognizer["members"]
    return None


def vocabulary(base_types: dict, composed_types: list | None = None) -> dict:
    """Construct a vocabulary. Returns ok(Vocabulary) or err(fault)."""
    coerced: dict[str, Recognizer] = {}
    for type_name, raw in base_types.items():
        coerced[type_name] = _coerce_recognizer(raw)

    # Reserved-word check on every Set/insensitive member (spec §2).
    for type_name, recognizer in coerced.items():
        members = _set_members(recognizer)
        if members is None:
            continue
        for member in members:
            layer = reservation_layer(member)
            if layer is not None:
                return err(fault(
                    "reserved_word_in_vocabulary",
                    f"vocabulary member {member!r} is a reserved word",
                    category="server",
                    detail={"word": member, "layer": layer},
                ))

    # Set-vs-Set overlap: a token must match at most one type (spec §3).
    set_types = [
        (name, _set_members(rec))
        for name, rec in coerced.items()
        if _set_members(rec) is not None
    ]
    for i in range(len(set_types)):
        name_a, members_a = set_types[i]
        for j in range(i + 1, len(set_types)):
            name_b, members_b = set_types[j]
            shared = members_a & members_b
            if shared:
                return err(fault(
                    "vocabulary_overlap",
                    f"types {name_a!r} and {name_b!r} share members {sorted(shared)}",
                    category="server",
                    detail={"types": [name_a, name_b], "members": sorted(shared)},
                ))

    vocab: Vocabulary = {
        "base_types": coerced,
        "composed_types": list(composed_types or []),
    }
    return ok(vocab)


def merge_vocabularies(*results: dict) -> dict:
    """Merge vocabularies (spec §3 Vocabulary Merge). Each argument is a
    Vocabulary (already-unwrapped). Returns ok(Vocabulary) or err(fault) on a
    type-name collision or a cross-vocabulary Set value collision."""
    merged_base: dict[str, Recognizer] = {}
    merged_composed: list[ComposedType] = []
    # Track which type owns each Set member, to catch value collisions.
    member_owner: dict[str, str] = {}

    for vocab in results:
        for type_name, recognizer in vocab["base_types"].items():
            if type_name in merged_base:
                return err(fault(
                    "vocabulary_merge_name_collision",
                    f"type {type_name!r} defined in more than one vocabulary",
                    category="server",
                    detail={"type": type_name},
                ))
            members = _set_members(recognizer)
            if members is not None:
                for member in members:
                    owner = member_owner.get(member)
                    if owner is not None and owner != type_name:
                        return err(fault(
                            "vocabulary_merge_value_collision",
                            f"member {member!r} appears under {owner!r} and {type_name!r}",
                            category="server",
                            detail={"member": member, "types": [owner, type_name]},
                        ))
                    member_owner[member] = type_name
            merged_base[type_name] = recognizer
        merged_composed.extend(vocab["composed_types"])

    return ok({"base_types": merged_base, "composed_types": merged_composed})
