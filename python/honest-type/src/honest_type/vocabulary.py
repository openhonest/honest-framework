"""Vocabulary and binding construction (sections 2, 3).

`vocabulary({...})` normalizes each declaration to a recognizer and validates at
construction time: no Set member may collide with a reserved word (section 2), and no two
Set types may share a value (section 3, Set x Set overlap). These are construction-time
checks (section 1.1), not honest-check rules. A failed check comes back as a Fault value,
never a raise: a pure function returns its error as data (section 11.2), so `vocabulary()`
and `merge()` return `Vocabulary | Fault`. Each `_check_*` returns the faults it found, an
empty list when clean (the honest-design idiom). Predicate-based overlaps and reserved-word
collisions are caught later (by honest-test / at classification).
"""

from itertools import combinations

from honest_type._util import _choose, _pick
from honest_type.recognizers import is_bounded, members, normalize, recognize
from honest_type.reserved import is_reserved, reservation_layer
from honest_type.types import fault


# A fixed, diverse corpus for catch-all detection (section 13.3): deterministic, not random — the
# constructor is pure and a recognizer near the 95% threshold must pass or fail identically every
# run. It varies length and character class so a genuinely discriminating recognizer accepts only a
# small fraction of it.
_CATCH_ALL_ALPHABET = "abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,-_/@#:!?'()[]{}<>=+*éüñλ—\t"
_CATCH_ALL_SAMPLE = ("",) + tuple(
    "".join(_CATCH_ALL_ALPHABET[(i * 31 + j * 17) % len(_CATCH_ALL_ALPHABET)] for j in range((i % 16) + 1))
    for i in range(1, 1000)
)


def maybe(slot: str) -> dict:
    """An optional binding slot (section 5): absent token -> Nothing, not a rejection."""
    return {"kind": "maybe", "slot": slot}


def is_maybe(slot_or_maybe) -> bool:
    return hasattr(slot_or_maybe, "get") and slot_or_maybe.get("kind") == "maybe"


def unwrap_maybe(slot_or_maybe) -> str:
    """The bare slot name, whether it was wrapped in maybe() or not."""
    return _pick(is_maybe(slot_or_maybe), lambda: slot_or_maybe["slot"], lambda: slot_or_maybe)


def composed(name: str, requires: dict, captures) -> dict:
    """A composed (multi-token) type (section 4): matches when `requires` base types are
    present with the given values; binds the `captures` base type's value to its slot.
    `captures` may be a bare type name or `maybe(type_name)`."""
    return {"name": name, "requires": dict(requires), "captures": captures}


def _reserved_fault(member):
    """The fault a reserved Set member raises, naming the member and the reservation layer."""
    layer = reservation_layer(member)
    return fault(
        "reserved_word_in_vocabulary",
        f"Set member '{member}' is a reserved word at the {layer} layer",
        "server", [], {"word": member, "layer": layer},
    )


def _check_reserved(base_types: dict) -> list:
    """The construction check that no Set member is a reserved word (section 2). Returns the faults
    it found, empty when clean."""
    bounded = filter(lambda item: is_bounded(item[1]), base_types.items())
    reserved_members = (
        member
        for type_name, recognizer in bounded
        for member in filter(is_reserved, members(recognizer))
    )
    return [_reserved_fault(member) for member in reserved_members]


def _overlap_fault(pair):
    """The fault two Set types that share values raise, naming both types and the shared values."""
    (name_a, members_a), (name_b, members_b) = pair
    shared = members_a & members_b
    return fault(
        "vocabulary_overlap",
        f"Types '{name_a}' and '{name_b}' share values {sorted(shared)} "
        "(a token must match exactly zero or one type).",
        "server", [], {"type_a": name_a, "type_b": name_b, "shared": sorted(shared)},
    )


def _check_overlap(base_types: dict) -> list:
    """The construction check that no token matches two Set types in one vocabulary (section 3).
    Returns the faults it found, empty when clean."""
    bounded = {name: members(rec) for name, rec in filter(lambda item: is_bounded(item[1]), base_types.items())}
    pairs = combinations(sorted(bounded.items()), 2)
    overlapping = filter(lambda pair: pair[0][1] & pair[1][1], pairs)
    return [_overlap_fault(pair) for pair in overlapping]


def _accepts(recognizer: dict, token: str) -> bool:
    """Whether a recognizer accepts a token during catch-all sampling (section 13.3). A predicate
    that raises on a sample string counts as not accepting it — the same tolerance classification
    applies at runtime (section 9.6) — so a non-total predicate is sampled, not propagated."""
    try:  # honest: ignore HC-P002: a sampled predicate throw is tolerated as a non-accept at the sampling boundary, not propagated (section 9.6)
        return bool(recognize(token, recognizer))
    except Exception:
        return False


def _accept_count(recognizer):
    """How many of the fixed catch-all sample a predicate recognizer accepts (section 13.3)."""
    return sum(map(lambda token: _accepts(recognizer, token), _CATCH_ALL_SAMPLE))


def _catch_all_fault(type_name, accepted):
    """The fault a predicate accepting nearly all inputs raises (section 13.3)."""
    return fault(
        "catch_all_recognizer",
        f"Type '{type_name}' accepts nearly all inputs ({accepted}/{len(_CATCH_ALL_SAMPLE)}) "
        "— not a discriminating type (HC011).",
        "server", [], {"type": type_name, "accepted": accepted, "sampled": len(_CATCH_ALL_SAMPLE)},
    )


def _check_catch_all(base_types: dict) -> list:
    """The construction check that no predicate recognizer accepts nearly all inputs (section 13.3):
    not a type but the absence of one. Each predicate is sampled against the fixed corpus; acceptance
    above 95% fails construction. Bounded Set recognizers are finite and exempt. Returns the faults it
    found, empty when clean."""
    predicates = filter(lambda item: not is_bounded(item[1]), base_types.items())
    counted = ((type_name, _accept_count(recognizer)) for type_name, recognizer in predicates)
    over = filter(lambda type_count: type_count[1] / len(_CATCH_ALL_SAMPLE) > 0.95, counted)
    return [_catch_all_fault(type_name, accepted) for type_name, accepted in over]


def _requires_faults(comp, base_names):
    """The faults a composed type's unknown required base types raise, in requires order."""
    unknown = filter(lambda required_type: required_type not in base_names, comp["requires"])
    return [
        fault(
            "unknown_composed_base",
            f"Composed type '{comp['name']}' requires unknown base type '{required_type}'.",
            "server", [], {"composed": comp["name"], "unknown_base": required_type},
        )
        for required_type in unknown
    ]


def _capture_faults(comp, base_names):
    """The fault a composed type's unknown captured base type raises, empty when the capture is
    a declared base type."""
    capture_type = unwrap_maybe(comp["captures"])
    return _choose(
        capture_type not in base_names,
        [fault(
            "unknown_composed_base",
            f"Composed type '{comp['name']}' captures unknown base type '{capture_type}'.",
            "server", [], {"composed": comp["name"], "unknown_base": capture_type},
        )],
        [],
    )


def _check_composed(base_types: dict, composed_list: list) -> list:
    """The construction check that every composed type's required and captured base types exist
    (section 4). Returns the faults it found, empty when clean."""
    base_names = set(base_types)
    return [
        found
        for comp in composed_list
        for found in (_requires_faults(comp, base_names) + _capture_faults(comp, base_names))
    ]


def _requires_subset(comp_a: dict, comp_b: dict) -> bool:
    """Whether one composed type's requirements are a subset of the other's (either direction)."""
    requires_a = set(comp_a["requires"].items())
    requires_b = set(comp_b["requires"].items())
    return requires_a <= requires_b or requires_b <= requires_a


def _captures_conflict(comp_a: dict, comp_b: dict) -> bool:
    """Whether two composed types are ambiguous at construction (section 4.3 no-ambiguity rule): they
    capture the same base type and one's requirements are a subset of the other's, so the subset
    fires whenever the superset does and a token of the captured type is captured by both. Disjoint
    requirements may still co-fire on some input, but that is input-dependent and left to honest-test.
    Pure."""
    return _pick(
        unwrap_maybe(comp_a["captures"]) != unwrap_maybe(comp_b["captures"]),
        lambda: False,
        lambda: _requires_subset(comp_a, comp_b),
    )


def _ambiguous_fault(pair):
    """The fault two composed types that would ambiguously capture one token raise (section 4.3)."""
    comp_a, comp_b = pair
    return fault(
        "ambiguous_capture",
        f"Composed types '{comp_a['name']}' and '{comp_b['name']}' both capture "
        f"'{unwrap_maybe(comp_a['captures'])}' under compatible requirements — a token would be "
        "ambiguously captured by both (section 4.3 no-ambiguity rule).",
        "server", [], {"composed_a": comp_a["name"], "composed_b": comp_b["name"]},
    )


def _check_capture_ambiguity(composed_list: list) -> list:
    """The construction check that no two composed types would ambiguously capture the same token
    (section 4.3). Returns the faults it found, empty when clean. Pure."""
    conflicting = filter(lambda pair: _captures_conflict(pair[0], pair[1]), combinations(composed_list, 2))
    return [_ambiguous_fault(pair) for pair in conflicting]


def _build_vocabulary(base_declarations: dict, composed_types) -> dict:
    """Normalize declarations and run every construction check, returning the first fault found or
    the validated vocabulary. Reached only once base_declarations is non-empty."""
    base_types = {name: normalize(declaration) for name, declaration in base_declarations.items()}
    composed_list = list(composed_types or [])
    found = next(iter(
        _check_reserved(base_types)
        + _check_overlap(base_types)
        + _check_catch_all(base_types)
        + _check_composed(base_types, composed_list)
        + _check_capture_ambiguity(composed_list)
    ), None)
    return _pick(
        found is not None,
        lambda: found,
        lambda: {"base_types": base_types, "composed_types": composed_list},
    )


def vocabulary(base_declarations: dict, composed_types=None) -> dict:
    """Build a validated vocabulary from {type_name: declaration}. Returns the vocabulary, or a Fault
    value when a check fails (section 11.2) — a pure function returns its error as data, never raises."""
    return _pick(
        not base_declarations,
        lambda: fault(
            "empty_vocabulary",
            "A vocabulary must declare at least one recognizer (Law HT-5): an empty "
            "vocabulary recognizes nothing and is non-conformant.",
            "server", [], {},
        ),
        lambda: _build_vocabulary(base_declarations, composed_types),
    )


def _type_names(vocab: dict) -> set:
    """Every type name a vocabulary defines — base and composed alike (they share one
    flat binding table, section 4.3)."""
    return set(vocab["base_types"]) | {comp["name"] for comp in vocab["composed_types"]}


def _merge_checked(vocab_a: dict, vocab_b: dict) -> dict:
    """Combine two name-disjoint vocabularies and run the cross-vocabulary checks, returning the
    first fault found or the merged vocabulary. Reached only once the names are known disjoint."""
    base_types = {**vocab_a["base_types"], **vocab_b["base_types"]}
    composed_list = [*vocab_a["composed_types"], *vocab_b["composed_types"]]
    found = next(iter(
        _check_overlap(base_types)  # cross-vocabulary Set x Set value collision (section 3)
        + _check_composed(base_types, composed_list)
        + _check_capture_ambiguity(composed_list)
    ), None)
    return _pick(
        found is not None,
        lambda: found,
        lambda: {"base_types": base_types, "composed_types": composed_list},
    )


def merge(vocab_a: dict, vocab_b: dict) -> dict:
    """Combine two vocabularies into one (section 3). Returns the merged vocabulary, or a Fault value
    on a name collision (a type defined by both) or a value collision (a Set member shared across the
    two under different type names) — data, not a raise. Predicate overlaps are left to honest-test."""
    shared_names = _type_names(vocab_a) & _type_names(vocab_b)
    return _pick(
        bool(shared_names),
        lambda: fault(
            "vocabulary_name_collision",
            f"Vocabularies both define type name(s) {sorted(shared_names)}.",
            "server", [], {"shared_names": sorted(shared_names)},
        ),
        lambda: _merge_checked(vocab_a, vocab_b),
    )


def binding(table: dict) -> dict:
    """A binding table mapping type names to slot names. Plain data."""
    return dict(table)


def auto_binding(vocab: dict) -> dict:
    """The identity binding: every type name (base and composed) is its own slot (section 6)."""
    out = {type_name: type_name for type_name in vocab["base_types"]}
    for composed in vocab["composed_types"]:
        out[composed["name"]] = composed["name"]
    return out
