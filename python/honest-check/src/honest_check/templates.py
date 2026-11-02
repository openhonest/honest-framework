"""The template class-reference extractor honest-check shares with honest-test (spec §3.5).

template_class_references is the public counterpart of the class extraction check_references
runs for HC-REF003 (§4.2): it reads one component template's bytes and returns one ClassRef
{ class } per static CSS class token the template references, so honest-test can prove two
components do not share a CSS namespace (honest-test §7.1). The template arrives as bytes, the
form honest-parse's parse takes and honest-test holds a component template in. A class value carrying
interpolation (class="card {{ variant }}") is dynamic and skipped whole, the stated bound of
the check. It opens no file, executes nothing, and raises nothing.
"""

from honest_parse import parse, walk

# The markers that make a class value dynamic. A value carrying any of them is interpolated
# and skipped whole, exactly as HC-REF003 skips it (§4.2).
_INTERPOLATION_MARKERS = ("{{", "}}", "{%", "%}")


def template_class_references(template):
    """One ClassRef { class } per static CSS class token the template references, in source
    order. The template bytes are read under the html grammar; each `class="..."` attribute's
    value is split on whitespace into tokens, and a value carrying interpolation is skipped
    whole. A template that references no static class yields the empty list."""
    references = []
    for node in walk(parse(template, "html").root_node):
        if node.type != "attribute":
            continue
        name_node = _first_child_of_type(node, "attribute_name")
        if name_node is None or name_node.text.decode("utf-8") != "class":
            continue
        value_node = _first_child_of_type(node, "quoted_attribute_value")
        if value_node is None:
            continue
        inner = _first_child_of_type(value_node, "attribute_value")
        if inner is None:
            continue
        value_text = inner.text.decode("utf-8")
        if _is_interpolated(value_text):
            continue
        for token in value_text.split():
            references.append({"class": token})
    return references


def _first_child_of_type(node, type_name):
    """The first named child of node whose type is type_name, or None when it has none."""
    return next(
        (child for child in node.named_children if child.type == type_name), None
    )


def _is_interpolated(text):
    """True when text carries a jinja interpolation marker, making the value dynamic."""
    return any(marker in text for marker in _INTERPOLATION_MARKERS)
