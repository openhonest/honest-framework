# scenario: _read_function omits pure_calls when no annotation is present
# inherits: hd=python/honest-design/honest-design.hd::_read_function -> feature=python/honest-design/features/honest-design.feature::_read_function omits pure_calls when no annotation is present

import honest_parse

_SOURCE = b'module example\n  fn identity : (value: str) -> str note "returns the value"\n'


def probe_read_function_absent_pure_calls():
    from honest_design.reader import _read_function

    root = honest_parse.parse(_SOURCE, "hd").root_node
    module = next(node for node in root.named_children if node.type == "module_decl")
    declaration = next(node for node in module.named_children if node.type == "function_decl")
    actual = _read_function(declaration, _SOURCE)
    return [] if "pure_calls" not in actual else [f"Unexpected pure_calls: {actual['pure_calls']!r}"]
