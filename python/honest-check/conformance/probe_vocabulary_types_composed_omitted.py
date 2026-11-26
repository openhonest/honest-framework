# scenario: vocabulary_types returns empty composed fields when declarations are omitted
# inherits: hd=python/honest-check/honest-check.hd::vocabulary_types -> feature=specs/features/honest-check.feature::vocabulary_types returns empty composed fields when declarations are omitted

_SOURCE = b"cards = vocabulary({'Part': {'head'}})\n"
_EXPECTED = {
    'base_names': {'Part'},
    'composed_type_names': set(),
    'composed': [],
}


def probe_vocabulary_types_composed_omitted():
    from honest_check import build_context, vocabulary_types

    context = build_context(_SOURCE, "cards.py", {})
    call = next(
        node for node in context["nodes"]
        if node.type == "call" and node.child_by_field_name("function").text == b"vocabulary"
    )
    surface = vocabulary_types(context, call)
    actual = {field: surface.get(field) for field in _EXPECTED}
    return [] if actual == _EXPECTED else [f"Expected {_EXPECTED!r}, received {actual!r}"]
