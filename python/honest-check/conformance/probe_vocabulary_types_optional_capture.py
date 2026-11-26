# scenario: vocabulary_types preserves the base name inside an optional capture
# inherits: hd=python/honest-check/honest-check.hd::vocabulary_types -> feature=specs/features/honest-check.feature::vocabulary_types preserves the base name inside an optional capture


def probe_vocabulary_types_optional_capture():
    from honest_check import build_context, vocabulary_types

    source = b"""from honest_type import composed, maybe, vocabulary
cards = vocabulary({"Part": {"part"}}, [
    composed("Combined", requires={}, captures=maybe("Part")),
    composed(dynamic_name, requires={}, captures=maybe("Part")),
])
"""
    ctx = build_context(source, "case.py", {})
    vocabulary = ctx["root"].named_children[-1].named_children[0].child_by_field_name("right")
    declarations = vocabulary.child_by_field_name("arguments").named_children[1]
    first_name = declarations.named_children[0].child_by_field_name("arguments").named_children[0]
    records = vocabulary_types(ctx, vocabulary)["composed"]
    actual = [
        (entry["captures_bases"], "name_node" in entry, entry.get("name_node"))
        for entry in records
    ]
    expected = [({"Part"}, True, first_name), ({"Part"}, True, None)]
    return [] if actual == expected else [f"optional capture records -> {actual!r}, expected {expected!r}"]
