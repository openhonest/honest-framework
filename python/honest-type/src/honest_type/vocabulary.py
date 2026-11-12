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
    return slot_or_maybe["slot"] if is_maybe(slot_or_maybe) else slot_or_maybe


def composed(name: str, requires: dict, captures) -> dict:
    """A composed (multi-token) type (section 4): matches when `requires` base types are
    present with the given values; binds the `captures` base type's value to its slot.
    `captures` may be a bare type name or `maybe(type_name)`."""
    return {"name": name, "requires": dict(requires), "captures": captures}


def _check_reserved(base_types: dict) -> list:
    """The construction check that no Set member is a reserved word (section 2). Returns the faults
    it found, empty when clean."""
    faults = []
    for type_name, recognizer in base_types.items():
        if not is_bounded(recognizer):
            continue
        for member in members(recognizer):
            if is_reserved(member):
                layer = reservation_layer(member)
                faults.append(fault(
                    "reserved_word_in_vocabulary",
                    f"Set member '{member}' is a reserved word at the {layer} layer",
                    "server", [], {"word": member, "layer": layer},
                ))
    return faults


def _check_overlap(base_types: dict) -> list:
    """The construction check that no token matches two Set types in one vocabulary (section 3).
    Returns the faults it found, empty when clean."""
    faults = []
    bounded = {name: members(rec) for name, rec in base_types.items() if is_bounded(rec)}
    for (name_a, members_a), (name_b, members_b) in combinations(sorted(bounded.items()), 2):
        shared = members_a & members_b
        if shared:
            faults.append(fault(
                "vocabulary_overlap",
                f"Types '{name_a}' and '{name_b}' share values {sorted(shared)} "
                "(a token must match exactly zero or one type).",
                "server", [], {"type_a": name_a, "type_b": name_b, "shared": sorted(shared)},
            ))
    return faults


# honest: disable HC-P002: a sampled predicate throw is tolerated, not propagated (section 9.6)
def _accepts(recognizer: dict, token: str) -> bool:
    """Whether a recognizer accepts a token during catch-all sampling (section 13.3). A predicate
    that raises on a sample string counts as not accepting it — the same tolerance classification
    applies at runtime (section 9.6) — so a non-total predicate is sampled, not propagated."""
    try:
        return bool(recognize(token, recognizer))
    except Exception:
        return False
# honest: enable HC-P002


def _check_catch_all(base_types: dict) -> list:
    """The construction check that no predicate recognizer accepts nearly all inputs (section 13.3):
    not a type but the absence of one. Each predicate is sampled against the fixed corpus; acceptance
    above 95% fails construction. Bounded Set recognizers are finite and exempt. Returns the faults it
    found, empty when clean."""
    faults = []
    for type_name, recognizer in base_types.items():
        if is_bounded(recognizer):
            continue
        accepted = sum(1 for token in _CATCH_ALL_SAMPLE if _accepts(recognizer, token))
        if accepted / len(_CATCH_ALL_SAMPLE) > 0.95:
            faults.append(fault(
                "catch_all_recognizer",
                f"Type '{type_name}' accepts nearly all inputs ({accepted}/{len(_CATCH_ALL_SAMPLE)}) "
                "— not a discriminating type (HC011).",
                "server", [], {"type": type_name, "accepted": accepted, "sampled": len(_CATCH_ALL_SAMPLE)},
            ))
    return faults


def _check_composed(base_types: dict, composed_list: list) -> list:
    """The construction check that every composed type's required and captured base types exist
    (section 4). Returns the faults it found, empty when clean."""
    faults = []
    base_names = set(base_types)
    for comp in composed_list:
        for required_type in comp["requires"]:
            if required_type not in base_names:
                faults.append(fault(
                    "unknown_composed_base",
                    f"Composed type '{comp['name']}' requires unknown base type '{required_type}'.",
                    "server", [], {"composed": comp["name"], "unknown_base": required_type},
                ))
        capture_type = unwrap_maybe(comp["captures"])
        if capture_type not in base_names:
            faults.append(fault(
                "unknown_composed_base",
                f"Composed type '{comp['name']}' captures unknown base type '{capture_type}'.",
                "server", [], {"composed": comp["name"], "unknown_base": capture_type},
            ))
    return faults


def _captures_conflict(comp_a: dict, comp_b: dict) -> bool:
    """Whether two composed types are ambiguous at construction (section 4.3 no-ambiguity rule): they
    capture the same base type and one's requirements are a subset of the other's, so the subset
    fires whenever the superset does and a token of the captured type is captured by both. Disjoint
    requirements may still co-fire on some input, but that is input-dependent and left to honest-test.
    Pure."""
    if unwrap_maybe(comp_a["captures"]) != unwrap_maybe(comp_b["captures"]):
        return False
    requires_a = set(comp_a["requires"].items())
    requires_b = set(comp_b["requires"].items())
    return requires_a <= requires_b or requires_b <= requires_a


def _check_capture_ambiguity(composed_list: list) -> list:
    """The construction check that no two composed types would ambiguously capture the same token
    (section 4.3). Returns the faults it found, empty when clean. Pure."""
    faults = []
    for comp_a, comp_b in combinations(composed_list, 2):
        if _captures_conflict(comp_a, comp_b):
            faults.append(fault(
                "ambiguous_capture",
                f"Composed types '{comp_a['name']}' and '{comp_b['name']}' both capture "
                f"'{unwrap_maybe(comp_a['captures'])}' under compatible requirements — a token would be "
                "ambiguously captured by both (section 4.3 no-ambiguity rule).",
                "server", [], {"composed_a": comp_a["name"], "composed_b": comp_b["name"]},
            ))
    return faults


def vocabulary(base_declarations: dict, composed_types=None) -> dict:
    """Build a validated vocabulary from {type_name: declaration}. Returns the vocabulary, or a Fault
    value when a check fails (section 11.2) — a pure function returns its error as data, never raises."""
    if not base_declarations:
        return fault(
            "empty_vocabulary",
            "A vocabulary must declare at least one recognizer (Law HT-5): an empty "
            "vocabulary recognizes nothing and is non-conformant.",
            "server", [], {},
        )
    base_types = {name: normalize(declaration) for name, declaration in base_declarations.items()}
    composed_list = list(composed_types or [])
    for found in (
        _check_reserved(base_types)
        + _check_overlap(base_types)
        + _check_catch_all(base_types)
        + _check_composed(base_types, composed_list)
        + _check_capture_ambiguity(composed_list)
    ):
        return found
    return {"base_types": base_types, "composed_types": composed_list}


def _type_names(vocab: dict) -> set:
    """Every type name a vocabulary defines — base and composed alike (they share one
    flat binding table, section 4.3)."""
    return set(vocab["base_types"]) | {comp["name"] for comp in vocab["composed_types"]}


def merge(vocab_a: dict, vocab_b: dict) -> dict:
    """Combine two vocabularies into one (section 3). Returns the merged vocabulary, or a Fault value
    on a name collision (a type defined by both) or a value collision (a Set member shared across the
    two under different type names) — data, not a raise. Predicate overlaps are left to honest-test."""
    shared_names = _type_names(vocab_a) & _type_names(vocab_b)
    if shared_names:
        return fault(
            "vocabulary_name_collision",
            f"Vocabularies both define type name(s) {sorted(shared_names)}.",
            "server", [], {"shared_names": sorted(shared_names)},
        )
    base_types = {**vocab_a["base_types"], **vocab_b["base_types"]}
    composed_list = [*vocab_a["composed_types"], *vocab_b["composed_types"]]
    for found in (
        _check_overlap(base_types)  # cross-vocabulary Set x Set value collision (section 3)
        + _check_composed(base_types, composed_list)
        + _check_capture_ambiguity(composed_list)
    ):
        return found
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
