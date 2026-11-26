# scenario: _read_function preserves repeated pure calls in source order
# inherits: hd=python/honest-design/honest-design.hd::_read_function -> feature=python/honest-design/features/honest-design.feature::_read_function preserves repeated pure calls in source order

import honest_parse

_SOURCE = b'module example\n  fn identity : (value: str) -> str    pure_call "utils.answer" pure_call "utils.other" pure_call "utils.answer" note "returns the value"\n'
_EXPECTED = ["utils.answer", "utils.other", "utils.answer"]


def probe_read_function_repeated_pure_calls():
    from honest_design.reader import _read_function

    root = honest_parse.parse(_SOURCE, "hd").root_node
    module = next(node for node in root.named_children if node.type == "module_decl")
    declaration = next(node for node in module.named_children if node.type == "function_decl")
    actual = _read_function(declaration, _SOURCE)
    observations = (actual.get("pure_calls"), actual.get("side_effects"))
    expected = (_EXPECTED, [])
    return [] if observations == expected else [
        f"Expected pure calls and side effects {expected!r}, received {observations!r}"
    ]
