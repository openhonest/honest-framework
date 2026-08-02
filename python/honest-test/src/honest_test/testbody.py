"""honest-test section 4.8 — Test-Body Honesty. A pure check that a test body does not rebind a call
target at runtime: the monkeypatch fixture, mock.patch / patch.object, setattr on an imported symbol, or a
direct attribute assignment on an imported symbol. Rebinding makes the tested call graph differ from
production — the test-time twin of honest-check HC-P018 (finite-testability.md section 6). Source in,
violations out; no I/O, no state. The collection-time pytest boundary that calls this is a separate step."""
from honest_parse import line_col, node_text, parse_python, walk

_REBIND_MESSAGE = (
    "This test rebinds a call target at runtime, so it exercises a different call graph than production. "
    "Pass the dependency as a parameter (config-as-parameters, I/O at the boundary) and assert on the pure "
    "function, or inject a boundary plug as an argument."
)


def test_body_violations(source):
    """The runtime-rebinding violations in a test module's source (section 4.8): each a dict with the
    1-based line, the column, and a message. Pure — same source, same violations. An empty list means the
    test body is honest, rebinding nothing. Rebinds scoped to imported symbols (mod.fn = ..., setattr(mod,
    ...)) so mutating a local test object (obj.field = ...) is left alone."""
    source_bytes = source.encode("utf-8")
    root = parse_python(source_bytes).root_node

    imported = set()
    for node in walk(root):
        if node.type not in ("import_statement", "import_from_statement"):
            continue
        module = node.child_by_field_name("module_name")
        for name in node.named_children:
            if module is not None and name.start_byte == module.start_byte:
                continue
            idents = [node_text(child, source_bytes) for child in walk(name) if child.type == "identifier"]
            if idents:
                imported.add(idents[-1] if name.type == "aliased_import" else idents[0])

    violating = []
    for node in walk(root):
        if node.type == "call":
            function = node.child_by_field_name("function")
            attribute = function.child_by_field_name("attribute") if function.type == "attribute" else None
            name = node_text(attribute, source_bytes) if attribute is not None else node_text(function, source_bytes)
            base = function.child_by_field_name("object") if function.type == "attribute" else None
            base_text = node_text(base, source_bytes) if base is not None else ""
            positional = node.child_by_field_name("arguments").named_children
            first_arg = positional[0] if positional else None
            first_imported = first_arg is not None and first_arg.type == "identifier" and node_text(first_arg, source_bytes) in imported
            if base_text == "monkeypatch" or name == "patch" or (name == "object" and base_text == "patch") or (name == "setattr" and first_imported):
                violating.append(node)
        if node.type == "assignment":
            left = node.child_by_field_name("left")
            base = left.child_by_field_name("object") if left.type == "attribute" else None
            if base is not None and base.type == "identifier" and node_text(base, source_bytes) in imported:
                violating.append(node)

    return [dict(zip(("line", "col"), line_col(node)), message=_REBIND_MESSAGE) for node in violating]
