# scenario: _read_function preserves the legacy edge role in column 1
# inherits: hd=python/honest-design/honest-design.hd::_read_function -> feature=python/honest-design/features/honest-design.feature::_read_function preserves the legacy edge role in column 1
import honest_parse

_SOURCE = b'module example\n  edge fn identity : (value: str) -> str note "returns the value"\n'
_EXPECTED = ("edge", 1)


def probe_read_function_legacy_edge():
    from honest_design.reader import _read_function

    root = honest_parse.parse(_SOURCE, "hd").root_node
    module = next(node for node in root.named_children if node.type == "module_decl")
    function = next(node for node in module.named_children if node.type == "function_decl")
    actual = _read_function(function, _SOURCE)
    role_and_column = (actual.get("role"), actual.get("column"))
    return [] if role_and_column == _EXPECTED else [
        f"Expected role and column {_EXPECTED!r}, received {role_and_column!r}"
    ]
