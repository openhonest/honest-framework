"""Vocabulary and binding construction (sections 2, 3).

`vocabulary({...})` normalizes each declaration to a recognizer and validates at
construction time: no Set member may collide with a reserved word (section 2), and no two
Set types may share a value (section 3, Set x Set overlap). These are construction-time
errors — runtime errors that fire when the vocabulary is built — not honest-check rules
(section 1.1). A failed check raises `VocabularyError`; predicate-based overlaps and
reserved-word collisions are caught later (by honest-test / at classification).
"""

from itertools import combinations

from honest_type.recognizers import is_bounded, members, normalize
from honest_type.reserved import is_reserved, reservation_layer


class VocabularyError(Exception):
    """A vocabulary that cannot be built: reserved-word, overlap, or unknown composed base."""


def maybe(slot: str) -> dict:
    """An optional binding slot (section 5): absent token -> Nothing, not a rejection."""
    return {"kind": "maybe", "slot": slot}


def is_maybe(slot_or_maybe) -> bool:
    return hasattr(slot_or_maybe, "get") and slot_or_maybe.get("kind") == "maybe"


def unwrap_maybe(slot_or_maybe) -> str:
    """The bare slot name, whether it was wrapped in maybe() or not."""
    return slot_or_maybe["slot"] if is_maybe(slot_or_maybe) else slot_or_maybe


def composed(name: str, requires: dict, captures) -> dict:
    """A composed (multi-token) type (section 4): matches when `requires` base types are
    present with the given values; binds the `captures` base type's value to its slot.
    `captures` may be a bare type name or `maybe(type_name)`."""
    return {"name": name, "requires": dict(requires), "captures": captures}


def _check_reserved(type_name: str, recognizer: dict) -> None:
    if not is_bounded(recognizer):
        return
    for member in members(recognizer):
        if is_reserved(member):
            raise VocabularyError(
                f"Type '{type_name}' uses reserved word '{member}' "
                f"(reserved at the {reservation_layer(member)} layer)."
            )


def _check_overlap(base_types: dict) -> None:
    bounded = {name: members(rec) for name, rec in base_types.items() if is_bounded(rec)}
    for (name_a, members_a), (name_b, members_b) in combinations(sorted(bounded.items()), 2):
        shared = members_a & members_b
        if shared:
            raise VocabularyError(
                f"Types '{name_a}' and '{name_b}' share values {sorted(shared)} "
                "(a token must match exactly zero or one type)."
            )


def _check_composed(base_types: dict, composed_list: list) -> None:
    base_names = set(base_types)
    for comp in composed_list:
        for required_type in comp["requires"]:
            if required_type not in base_names:
                raise VocabularyError(
                    f"Composed type '{comp['name']}' requires unknown base type '{required_type}'."
                )
        capture_type = unwrap_maybe(comp["captures"])
        if capture_type not in base_names:
            raise VocabularyError(
                f"Composed type '{comp['name']}' captures unknown base type '{capture_type}'."
            )


def vocabulary(base_declarations: dict, composed_types=None) -> dict:
    """Build a validated vocabulary from {type_name: declaration}. Raises VocabularyError."""
    if not base_declarations:
        raise VocabularyError(
            "A vocabulary must declare at least one recognizer (Law HT-5): an empty "
            "vocabulary recognizes nothing and is non-conformant."
        )
    base_types = {name: normalize(declaration) for name, declaration in base_declarations.items()}
    for type_name, recognizer in base_types.items():
        _check_reserved(type_name, recognizer)
    _check_overlap(base_types)
    composed_list = list(composed_types or [])
    _check_composed(base_types, composed_list)
    return {"base_types": base_types, "composed_types": composed_list}


def _type_names(vocab: dict) -> set:
    """Every type name a vocabulary defines — base and composed alike (they share one
    flat binding table, section 4.3)."""
    return set(vocab["base_types"]) | {comp["name"] for comp in vocab["composed_types"]}


def merge(vocab_a: dict, vocab_b: dict) -> dict:
    """Combine two vocabularies into one (section 3). Fails at construction time on a name
    collision (a type defined by both) or a value collision (a Set member shared across the
    two under different type names). Predicate overlaps are left to honest-test."""
    shared_names = _type_names(vocab_a) & _type_names(vocab_b)
    if shared_names:
        raise VocabularyError(
            f"Vocabularies both define type name(s) {sorted(shared_names)}."
        )
    base_types = {**vocab_a["base_types"], **vocab_b["base_types"]}
    composed_list = [*vocab_a["composed_types"], *vocab_b["composed_types"]]
    _check_overlap(base_types)  # cross-vocabulary Set x Set value collision (section 3)
    _check_composed(base_types, composed_list)
    return {"base_types": base_types, "composed_types": composed_list}


def binding(table: dict) -> dict:
    """A binding table mapping type names to slot names. Plain data."""
    return dict(table)


def auto_binding(vocab: dict) -> dict:
    """The identity binding: every type name (base and composed) is its own slot (section 6)."""
    out = {type_name: type_name for type_name in vocab["base_types"]}
    for composed in vocab["composed_types"]:
        out[composed["name"]] = composed["name"]
    return out
