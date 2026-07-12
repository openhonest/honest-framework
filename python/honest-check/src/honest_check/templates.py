"""HTML/HTMX template scanning for HC002's boundary-vocabulary derivation (honest-page spec sections
5, 9, 10.3).

A chain's input boundary is the set of fields the templates targeting its route send: the form field
names, the hx-vals keys, and the application-state manifest keys. These are read statically from the
parsed template, never by running the application — the input boundary is closed (framework spec, "The
input boundary is closed"). Parsing is honest-parse's single boundary; this module only walks the
trees. Template file reading stays at the caller's I/O boundary — every function here takes source in.
"""

from honest_parse import line_col, node_text, parse_html, parse_javascript, parse_jinja, walk

# The Jinja composition tags whose target must resolve to a template (HC-REF002, honest-check §4.2).
_INCLUDING_TAGS = frozenset({"include", "extends"})

# HTMX request attributes -> HTTP method (honest-page section 9: hx-post / hx-get name a path).
_HX_METHOD = {"hx-post": "POST", "hx-get": "GET", "hx-put": "PUT", "hx-patch": "PATCH", "hx-delete": "DELETE"}
# Elements whose `name` submits a value within a form (honest-page section 9: form field names).
_FORM_CONTROLS = frozenset({"input", "select", "textarea", "button"})


def _open_tag(element):
    """The start tag (or self-closing tag) of an element node — the child that carries its attributes."""
    for child in element.children:
        if child.type in ("start_tag", "self_closing_tag"):
            return child
    return None


def _tag_name(element, source: bytes):
    """The tag name of an element (`form`, `input`), or None when it has no open tag."""
    tag = _open_tag(element)
    if tag is None:
        return None
    return next((node_text(c, source) for c in tag.children if c.type == "tag_name"), None)


def _attr(element, name: str, source: bytes):
    """The value of a named attribute on an element's open tag, or None when absent. The value sits
    under a quoted_attribute_value wrapper, so the attribute subtree is searched rather than its direct
    children. A present-but-valueless attribute reads as the empty string."""
    tag = _open_tag(element)
    if tag is None:
        return None
    for attribute in tag.children:
        if attribute.type != "attribute":
            continue
        attr_name = next((node_text(c, source) for c in walk(attribute) if c.type == "attribute_name"), None)
        if attr_name != name:
            continue
        return next((node_text(c, source) for c in walk(attribute) if c.type == "attribute_value"), "")
    return None


def _is_resolvable(value: str) -> bool:
    """A template attribute value is statically resolvable when it carries no template or JavaScript
    interpolation — `{{ }}`, `{% %}`, or `${ }` make the boundary unknowable (honest-page section 9)."""
    return "{{" not in value and "{%" not in value and "${" not in value


def _object_keys(object_node, source: bytes) -> frozenset:
    """The top-level keys of a JavaScript object literal, whether written as bare identifiers
    (`{search: ...}`) or as strings (`{"search": ...}`)."""
    keys = set()
    for pair in object_node.children:
        if pair.type != "pair":
            continue
        key = pair.children[0]
        keys.add(node_text(key, source).strip("\"'") if key.type == "string" else node_text(key, source))
    return frozenset(keys)


def _hx_vals_keys(raw) -> frozenset:
    """The top-level keys of an hx-vals attribute value, parsed as a JavaScript object. Empty when the
    attribute is absent or its value is not a static object (e.g. an hx-vals `js:{...}` form)."""
    if raw is None:
        return frozenset()
    wrapped = ("(" + raw + ")").encode("utf-8")
    for node in walk(parse_javascript(wrapped).root_node):
        if node.type == "object":
            return _object_keys(node, wrapped)
    return frozenset()


def _form_field_names(element, source: bytes) -> frozenset:
    """The `name`s of the form controls within an element (honest-page section 9: a form submits its
    field names) — input, select, textarea, and named buttons at any depth under the element."""
    # A non-element node has no tag name, so _tag_name returns None and it is skipped — no element
    # type guard is needed here, the total helpers filter it.
    names = set()
    for node in walk(element):
        if _tag_name(node, source) in _FORM_CONTROLS:
            value = _attr(node, "name", source)
            if value is not None:
                names.add(value)
    return frozenset(names)


def manifest_keys(root, source: bytes) -> frozenset:
    """The keys declared in a `const appManifest = { ... }` object (honest-page section 5.1) — the
    application-state slots domx sends as _state on every request in the manifest's scope. Empty when
    the parsed source declares no appManifest object."""
    for node in walk(root):
        if node.type != "variable_declarator":
            continue
        if node_text(node.child_by_field_name("name"), source) != "appManifest":
            continue
        value = node.child_by_field_name("value")
        if value is not None and value.type == "object":
            return _object_keys(value, source)
    return frozenset()


def request_sites(root, source: bytes) -> tuple:
    """Every HTMX request-sending site in a parsed template: the (method, path) its hx-* attribute
    names, whether that path is statically resolvable, and the fields it sends — its form field names
    unioned with its hx-vals keys (honest-page section 9)."""
    # A non-element node yields no attribute value, so _attr returns None and no site is made — the
    # total helper filters non-elements without a type guard.
    sites = []
    for node in walk(root):
        for attribute_name, method in _HX_METHOD.items():
            path = _attr(node, attribute_name, source)
            if path is None:
                continue
            fields = _form_field_names(node, source) | _hx_vals_keys(_attr(node, "hx-vals", source))
            sites.append({"method": method, "path": path, "resolvable": _is_resolvable(path), "fields": fields, "location": line_col(node)})
    return tuple(sites)


def template_includes(source: bytes) -> tuple:
    """Every `{% include %}`/`{% extends %}` reference in a template (HC-REF002): its `tag`, its literal
    `targets` (every string argument, quotes and whitespace stripped — one for a plain include, more for a
    conditional `{% include "a" if x else "b" %}` where both branches must resolve, none for a dynamic
    variable target), and the site `location` at the tag keyword. Read through honest-parse's Jinja
    grammar, which the HTML grammar cannot supply (it reads `{% %}` as opaque text). Pure."""
    out = []
    for node in walk(parse_jinja(source).root_node):
        # Only a `statement` node carries a `tag` field; every other node yields None here and is skipped,
        # so this single guard covers both non-statements and non-include/extends tags.
        tag = node.child_by_field_name("tag")
        if tag is None or node_text(tag, source) not in _INCLUDING_TAGS:
            continue
        targets = tuple(node_text(child, source).strip().strip("\"'") for child in node.children if child.type == "string")
        out.append({"tag": node_text(tag, source), "targets": targets, "location": line_col(tag)})
    return tuple(out)


def scan_template(source: bytes, path: str = "") -> dict:
    """Scan a rendered HTML/HTMX template for the boundary derivation (HC002) and reference resolution
    (HC-REF001): its request sites — each with the location of its action, so a dead reference is reported
    where it is authored — and the application-state manifest keys declared in its <script> blocks. `path`
    is the template's own path, carried so HC-REF001 can name it. Parsing is honest-parse's; this reads the
    trees. Source is passed in — template file reading stays at the caller's I/O boundary."""
    root = parse_html(source).root_node
    keys = set()
    for node in walk(root):
        if node.type != "script_element":
            continue
        for child in node.children:
            if child.type == "raw_text":
                script = node_text(child, source).encode("utf-8")
                keys = keys | manifest_keys(parse_javascript(script).root_node, script)
    return {"path": path, "sites": request_sites(root, source), "manifest_keys": frozenset(keys), "includes": template_includes(source)}
