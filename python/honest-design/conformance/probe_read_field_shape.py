# scenario: _read_name_and_type folds a record field into a Field
# inherits: hd=python/honest-design/honest-design.hd::_read_name_and_type -> feature=python/honest-design/features/honest-design.feature::_read_name_and_type folds a record field into a Field
import honest_parse

_SOURCE = b"module example\n  type Shape = { values: list<str> | NOTHING }\n"
_EXPECTED = {
    "name": "values",
    "type": [
        {"name": "list", "args": [[{"name": "str", "args": []}]]},
        {"name": "NOTHING", "args": []},
    ],
}


def probe_read_field_shape():
    from honest_design.reader import _read_name_and_type

    root = honest_parse.parse(_SOURCE, "hd").root_node
    module = next(node for node in root.named_children if node.type == "module_decl")
    declaration = next(node for node in module.named_children if node.type == "type_decl")
    value = declaration.child_by_field_name("value")
    field = next(node for node in value.named_children if node.type == "field")
    actual = _read_name_and_type(field, _SOURCE)
    return [] if actual == _EXPECTED else [f"Expected {_EXPECTED!r}, received {actual!r}"]
