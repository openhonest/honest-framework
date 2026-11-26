# scenario: _read_version preserves the architect's free-text version
# inherits: hd=python/honest-design/honest-design.hd::_read_version -> feature=python/honest-design/features/honest-design.feature::_read_version preserves the architect's free-text version
import honest_parse

_CASES = [
    (b'module example\n  version "release candidate + 7"\n', "release candidate + 7"),
    (b'module example\n  version "1.0-beta"\n', "1.0-beta"),
]


def probe_read_version():
    from honest_design.reader import _read_version

    failures = []
    for source, expected in _CASES:
        root = honest_parse.parse(source, "hd").root_node
        module = next(node for node in root.named_children if node.type == "module_decl")
        version = next(node for node in module.named_children if node.type == "version_decl")
        actual = _read_version(version, source)
        if actual != expected:
            failures.append(f"Expected {expected!r}, received {actual!r}")
    return failures
