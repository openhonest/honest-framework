# scenario: _read_pure_call returns the target without enclosing quotes
# inherits: hd=python/honest-design/honest-design.hd::_read_pure_call -> feature=python/honest-design/features/honest-design.feature::_read_pure_call returns the target without enclosing quotes

import honest_parse

_SOURCE = b'module example\n  fn identity : (value: str) -> str    pure_call "utils.answer" note "returns the value"\n'
_EXPECTED = "utils.answer"


def probe_read_pure_call_target():
    from honest_design.reader import _read_pure_call

    root = honest_parse.parse(_SOURCE, "hd").root_node
    module = next(node for node in root.named_children if node.type == "module_decl")
    declaration = next(node for node in module.named_children if node.type == "function_decl")
    annotation = next(node for node in declaration.named_children if node.type == "pure_call")
    actual = _read_pure_call(annotation, _SOURCE)
    return [] if actual == _EXPECTED else [f"Expected {_EXPECTED!r}, received {actual!r}"]
