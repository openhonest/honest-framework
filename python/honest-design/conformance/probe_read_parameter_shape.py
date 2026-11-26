# scenario: _read_name_and_type folds a function parameter into a Param
# inherits: hd=python/honest-design/honest-design.hd::_read_name_and_type -> feature=python/honest-design/features/honest-design.feature::_read_name_and_type folds a function parameter into a Param
import honest_parse

_SOURCE = b'module example\n  fn run : (value: NOTHING | str | int) -> bool note "reads a value"\n'
_EXPECTED = {
    "name": "value",
    "type": [
        {"name": "NOTHING", "args": []},
        {"name": "str", "args": []},
        {"name": "int", "args": []},
    ],
}


def probe_read_parameter_shape():
    from honest_design.reader import _read_name_and_type

    root = honest_parse.parse(_SOURCE, "hd").root_node
    module = next(node for node in root.named_children if node.type == "module_decl")
    function = next(node for node in module.named_children if node.type == "function_decl")
    signature = next(node for node in function.named_children if node.type == "signature")
    params = next(node for node in signature.named_children if node.type == "params")
    param = next(node for node in params.named_children if node.type == "param")
    actual = _read_name_and_type(param, _SOURCE)
    return [] if actual == _EXPECTED else [f"Expected {_EXPECTED!r}, received {actual!r}"]
