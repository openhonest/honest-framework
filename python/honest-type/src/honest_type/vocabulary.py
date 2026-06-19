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
    """A vocabulary that cannot be built: reserved-word or overlap collision (sections 2, 3)."""


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


def vocabulary(base_declarations: dict, composed_types=None) -> dict:
    """Build a validated vocabulary from {type_name: declaration}. Raises VocabularyError."""
    base_types = {name: normalize(declaration) for name, declaration in base_declarations.items()}
    for type_name, recognizer in base_types.items():
        _check_reserved(type_name, recognizer)
    _check_overlap(base_types)
    return {"base_types": base_types, "composed_types": list(composed_types or [])}


def binding(table: dict) -> dict:
    """A binding table mapping type names to slot names. Plain data."""
    return dict(table)


def auto_binding(vocab: dict) -> dict:
    """The identity binding: every type name (base and composed) is its own slot (section 6)."""
    out = {type_name: type_name for type_name in vocab["base_types"]}
    for composed in vocab["composed_types"]:
        out[composed["name"]] = composed["name"]
    return out
