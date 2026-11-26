# scenario: _read_module preserves the authored version
# inherits: hd=python/honest-design/honest-design.hd::_read_module -> feature=python/honest-design/features/honest-design.feature::_read_module preserves the authored version
import honest_parse

_SOURCE = b'module example\n  version "internal preview 7"\n'
_EXPECTED = "internal preview 7"


def probe_read_module_authored_version():
    from honest_design.reader import _read_module

    root = honest_parse.parse(_SOURCE, "hd").root_node
    module = next(node for node in root.named_children if node.type == "module_decl")
    actual = _read_module(module, _SOURCE).get("version")
    return [] if actual == _EXPECTED else [f"Expected version {_EXPECTED!r}, received {actual!r}"]
