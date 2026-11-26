# scenario: vocabulary_types preserves composed names from positional declarations
# inherits: hd=python/honest-check/honest-check.hd::vocabulary_types -> feature=specs/features/honest-check.feature::vocabulary_types preserves composed names from positional declarations

_SOURCE = b"cards = vocabulary({'Part': {'head'}, 'Value': {'tail'}}, [composed('Combined', {'Part': 'head'}, 'Value')])\n"
_EXPECTED = {
    'base_names': {'Value', 'Part'},
    'composed_type_names': {'Combined'},
    'composed': [{'requires_bases': {'Part'}, 'captures_bases': {'Value'}}],
}


def probe_vocabulary_types_composed_positional():
    from honest_check import build_context, vocabulary_types

    context = build_context(_SOURCE, "cards.py", {})
    call = next(
        node for node in context["nodes"]
        if node.type == "call" and node.child_by_field_name("function").text == b"vocabulary"
    )
    declaration = next(
        node for node in context["nodes"]
        if node.type == "call" and node.child_by_field_name("function").text == b"composed"
    )
    name_node = declaration.child_by_field_name("arguments").named_children[0]
    expected = {
        **_EXPECTED,
        "composed": [{**_EXPECTED["composed"][0], "name_node": name_node}],
    }
    surface = vocabulary_types(context, call)
    actual = {field: surface.get(field) for field in expected}
    return [] if actual == expected else [f"Expected {expected!r}, received {actual!r}"]
