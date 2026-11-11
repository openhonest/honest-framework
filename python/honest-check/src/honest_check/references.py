"""honest-check the whole-set cross-file reference core (HC-REF002, HC-REF003), split from core.py so no module is a god-file (L1.17).

The per-rule logic nests here as data exactly as it did in core.py; the exact Diagnostic each
rule produces is pinned by the conformance suite (section 9.2), not by a separately declared
function."""

import ast
import re
from honest_parse import language_of, line_col, parse, parse_source, walk
from honest_check.constants import _CLASSLIST_METHODS, _INTERPOLATION_MARKERS, _TEMPLATE_GRAMMARS

# The HTMX action attributes HC-REF001 reads: each names the HTTP method in its suffix
# and the target path in its value. Attributes like hx-swap, hx-target and hx-ext carry no
# (method, path) action and are not sites.
_ACTION_ATTRS = {
    "hx-get": "GET",
    "hx-post": "POST",
    "hx-put": "PUT",
    "hx-delete": "DELETE",
    "hx-patch": "PATCH",
}


def check_references(sources, format_vocabulary):
    """The pure cross-file reference core of the base-mode CLI path (§HC-REF002,
    §HC-REF003), the whole-set counterpart of check_source for references that resolve
    across files rather than within one.

    sources is a list of SourceFile ({path, text}) — the discovered template, stylesheet
    and script files, already read and paired. A template's `{% include %}` target may
    resolve to any template in the set, and a class a template or script names may be
    defined by any stylesheet, so neither reference is decidable from one file: the whole
    set must be in view. It opens no file and raises nothing — a dead reference comes back
    as an error Diagnostic.

    A template carries both kinds of reference, and no single grammar surfaces both: the
    jinja grammar reads `{% %}` tags but leaves HTML attributes as opaque template_data,
    and the html grammar reads class attributes but leaves `{% %}` as opaque text (§HC-REF002).
    So a template is parsed under jinja for its include/extends targets and under html for
    its class attributes. Stylesheets parse under css, scripts under javascript.

    The per-rule logic is nested here as data, exactly as check_source holds its construction
    rules; HC-REF002 and HC-REF003 are not separately declared functions.
    """

    def finding(rule_id, message, path, node):
        line, col = line_col(node)
        return {
            "rule_id": rule_id,
            "severity": "error",
            "message": message,
            "source_location": f"{path}:{line}:{col}",
            "context": "",
            "fixable": False,
        }

    def root_under(text, grammar):
        """The parse tree root of text read under a named grammar. Unlike check_source's
        parse_source, which detects the grammar from the path, a template is read under two
        grammars whichever extension it carries, so the grammar is chosen here, not detected
        from a path."""
        return parse(text.encode("utf-8"), grammar).root_node

    def basename(path):
        return path.rsplit("/", 1)[-1]

    def literal_text(string_node):
        """The string a jinja `string` node spells, surrounding whitespace and quotes
        stripped."""
        return ast.literal_eval(string_node.text.decode("utf-8").strip())

    def is_interpolated(text):
        return any(marker in text for marker in _INTERPOLATION_MARKERS)

    def js_string_value(string_node):
        """The value a javascript `string` node spells, read from its string_fragment; the
        empty string for a string with no fragment (`""`)."""
        fragment = next(
            (c for c in string_node.named_children if c.type == "string_fragment"), None
        )
        return fragment.text.decode("utf-8") if fragment is not None else ""

    def kind_of(source_file):
        """The reference kind of one source file from the grammar honest-parse detects:
        'template', 'stylesheet', 'script', or None for a file carrying no reference this
        core resolves. A file of an unplaceable extension resolves to None and is ignored."""
        detected = language_of(source_file["path"]).get("ok")
        if detected in _TEMPLATE_GRAMMARS:
            return "template"
        if detected == "css":
            return "stylesheet"
        if detected == "javascript":
            return "script"
        return None

    templates = [s for s in sources if kind_of(s) == "template"]
    stylesheets = [s for s in sources if kind_of(s) == "stylesheet"]
    scripts = [s for s in sources if kind_of(s) == "script"]
    code_sources = [
        s for s in sources if language_of(s["path"]).get("ok") == "python"
    ]

    def html_attributes(text):
        """(name, value_text, attribute_node) for each HTML attribute carrying a quoted
        value, read under the html grammar: the attribute's name, the raw text of its value,
        and the attribute node itself (whose span starts at the name, so a diagnostic points
        at the attribute). HC-REF001 and HC-REF004 read their sites off this one pass."""
        attributes = []
        for node in walk(root_under(text, "html")):
            if node.type != "attribute":
                continue
            name_node = next(
                (c for c in node.named_children if c.type == "attribute_name"), None
            )
            value_node = next(
                (c for c in node.named_children if c.type == "quoted_attribute_value"),
                None,
            )
            if name_node is None or value_node is None:
                continue
            inner = next(
                (c for c in value_node.named_children if c.type == "attribute_value"),
                None,
            )
            if inner is None:
                continue
            attributes.append(
                (name_node.text.decode("utf-8"), inner.text.decode("utf-8"), node)
            )
        return attributes

    def normalize_path(path):
        """A path with its interpolated and parameterized segments collapsed to one
        placeholder, so a template's `/items/{{item.id}}` and a route's `/items/{id}` compare
        equal. Jinja interpolation (`{{ ... }}`) is collapsed first, then a route parameter
        (`{ ... }`)."""
        path = re.sub(r"\{\{.*?\}\}", "{}", path)
        return re.sub(r"\{[^}]*\}", "{}", path)

    def is_dynamic_path(value):
        """True when an action value carries no literal path to resolve — a fully dynamic
        expression like `{{ url }}`. A value with literal path characters outside its
        interpolation (`/items/{{item.id}}`) is not dynamic and resolves through
        normalize_path, the same bound HC-REF002 takes for a variable include target."""
        outside = re.sub(r"\{\{.*?\}\}", "", value)
        return "{{" in value and not any(ch.isalnum() for ch in outside)

    # ---- HC-REF002: template include/extends target resolves to a template ----

    template_paths = {t["path"] for t in templates}
    template_basenames = {basename(path) for path in template_paths}

    def include_resolves(target):
        """Flat path equality against the template files in the set: the target resolves if
        it equals a template file's path or basename, or its own basename matches one
        (§HC-REF002). Nested template-search-root resolution (atoms/, molecules/ sibling
        roots) is out of scope — the .hd and spec do not pin how a pure function derives
        those roots from `sources` alone — so only flat matching is done here."""
        return (
            target in template_paths
            or target in template_basenames
            or basename(target) in template_basenames
        )

    def include_extends_statements(text):
        """(keyword, target, node) for each `{% include %}` / `{% extends %}` whose target
        is a string literal, read under the jinja grammar. A dynamic target (no string
        literal, `{% include some_var %}`) carries nothing to resolve and is skipped."""
        statements = []
        for node in walk(root_under(text, "jinja")):
            if node.type != "statement":
                continue
            tag = node.child_by_field_name("tag")
            keyword = tag.text.decode("utf-8")
            if keyword not in ("include", "extends"):
                continue
            string_node = next(
                (c for c in node.named_children if c.type == "string"), None
            )
            if string_node is None:
                continue
            statements.append((keyword, literal_text(string_node), node))
        return statements

    def check_ref002():
        findings = []
        for template in templates:
            for keyword, target, node in include_extends_statements(template["text"]):
                if include_resolves(target):
                    continue
                findings.append(
                    finding(
                        "HC-REF002",
                        f"template {keyword} target {target!r} resolves to no template among "
                        "the checked files. Add the template, or correct the target.",
                        template["path"],
                        node,
                    )
                )
        return findings

    # ---- HC-REF003: class reference resolves to a defined rule ----

    def defined_classes():
        """The union of class names every stylesheet in the set defines: a `class_name`
        under a `class_selector`, read under the css grammar. The `class_name` of a
        pseudo-class (`:hover`) sits under a pseudo_class_selector, not a class_selector, so
        it is not mistaken for a class."""
        classes = set()
        for sheet in stylesheets:
            for node in walk(root_under(sheet["text"], "css")):
                if (
                    node.type == "class_name"
                    and node.parent is not None
                    and node.parent.type == "class_selector"
                ):
                    classes.add(node.text.decode("utf-8"))
        return classes

    def template_class_tokens(text):
        """(token, node) for each static class token a template emits, read under the html
        grammar. A class value carrying interpolation (`class="card {{ variant }}"`) is
        skipped whole, the stated bound of the check."""
        tokens = []
        for node in walk(root_under(text, "html")):
            if node.type != "attribute":
                continue
            name_node = next(
                (c for c in node.named_children if c.type == "attribute_name"), None
            )
            if name_node is None or name_node.text.decode("utf-8") != "class":
                continue
            value_node = next(
                (c for c in node.named_children if c.type == "quoted_attribute_value"),
                None,
            )
            if value_node is None:
                continue
            inner = next(
                (c for c in value_node.named_children if c.type == "attribute_value"),
                None,
            )
            if inner is None:
                continue
            value_text = inner.text.decode("utf-8")
            if is_interpolated(value_text):
                continue
            for token in value_text.split():
                tokens.append((token, value_node))
        return tokens

    def classlist_tokens(call_node):
        """The class tokens one call contributes when it is a classList method call
        (el.classList.<method>(...)): each string-literal argument is one class token. A
        non-literal argument carries no literal and is skipped; a call that is not a
        classList method call contributes nothing."""
        function = call_node.child_by_field_name("function")
        if function is None or function.type != "member_expression":
            return []
        method = function.child_by_field_name("property")
        receiver = function.child_by_field_name("object")
        if method is None or method.text.decode("utf-8") not in _CLASSLIST_METHODS:
            return []
        if receiver is None or receiver.type != "member_expression":
            return []
        receiver_property = receiver.child_by_field_name("property")
        if (
            receiver_property is None
            or receiver_property.text.decode("utf-8") != "classList"
        ):
            return []
        arguments = call_node.child_by_field_name("arguments")
        return [
            (js_string_value(argument), call_node)
            for argument in arguments.named_children
            if argument.type == "string"
        ]

    def classname_tokens(assignment_node):
        """The class tokens one assignment contributes when it assigns a string literal to a
        `.className` property: each whitespace-separated token of the string. A non-literal
        right-hand side carries no literal and is skipped."""
        left = assignment_node.child_by_field_name("left")
        right = assignment_node.child_by_field_name("right")
        if left is None or left.type != "member_expression":
            return []
        if right is None or right.type != "string":
            return []
        left_property = left.child_by_field_name("property")
        if left_property is None or left_property.text.decode("utf-8") != "className":
            return []
        return [(token, assignment_node) for token in js_string_value(right).split()]

    def script_class_tokens(text):
        """(token, node) for each static class a script names, read under the javascript
        grammar: a string-literal argument to a classList method and each token of a
        className string-literal assignment."""
        tokens = []
        for node in walk(root_under(text, "javascript")):
            if node.type == "call_expression":
                tokens.extend(classlist_tokens(node))
            elif node.type == "assignment_expression":
                tokens.extend(classname_tokens(node))
        return tokens

    def check_ref003():
        classes = defined_classes()
        findings = []

        def report(source_file, tokens):
            return [
                finding(
                    "HC-REF003",
                    f"class {token!r} resolves to no rule any stylesheet defines. Define "
                    "the class, or correct the reference.",
                    source_file["path"],
                    node,
                )
                for token, node in tokens
                if token not in classes
            ]

        for template in templates:
            findings.extend(report(template, template_class_tokens(template["text"])))
        for script in scripts:
            findings.extend(report(script, script_class_tokens(script["text"])))
        return findings

    # ---- HC-REF001: template action target resolves to a mounted route ----

    def py_string_value(string_node):
        """The value a python `string` literal node spells, quotes and prefix resolved."""
        return ast.literal_eval(string_node.text.decode("utf-8"))

    def route_map():
        """(declared, routes): whether any code file declares a route_table() at all, and the
        set of (METHOD, normalized_path) pairs those route tables declare as data. honest-page
        writes route_table() as module-level data a tool reads by parsing (honest-page §9), so
        the route map is read here without running the application. `declared` is what gates
        HC-REF001: with no route_table in view the route map is absent, not empty, so the rule
        stands down rather than flag every action site."""
        declared = False
        routes = set()
        for code in code_sources:
            for node in walk(root_under(code["text"], "python")):
                if node.type != "function_definition":
                    continue
                name_node = node.child_by_field_name("name")
                if name_node is None or name_node.text.decode("utf-8") != "route_table":
                    continue
                declared = True
                for literal in walk(node):
                    if literal.type != "dictionary":
                        continue
                    pairs = {}
                    for pair in literal.named_children:
                        if pair.type != "pair":
                            continue
                        key = pair.child_by_field_name("key")
                        value = pair.child_by_field_name("value")
                        if (
                            key is None
                            or value is None
                            or key.type != "string"
                            or value.type != "string"
                        ):
                            continue
                        pairs[py_string_value(key)] = py_string_value(value)
                    if "method" in pairs and "path" in pairs:
                        routes.add(
                            (pairs["method"].upper(), normalize_path(pairs["path"]))
                        )
        return declared, routes

    def check_ref001():
        declared, routes = route_map()
        if not declared:
            return []
        findings = []
        for template in templates:
            for name, value, node in html_attributes(template["text"]):
                method = _ACTION_ATTRS.get(name)
                if method is None or is_dynamic_path(value):
                    continue
                if (method, normalize_path(value)) in routes:
                    continue
                findings.append(
                    finding(
                        "HC-REF001",
                        f"template action targets {method} {value!r}, which no route "
                        "mounts. Point it at a mounted route, or add the route.",
                        template["path"],
                        node,
                    )
                )
        return findings

    # ---- HC-REF004: behavioural hf-* value resolves to a declared vocabulary member ----

    def check_ref004():
        if format_vocabulary is None:
            return []
        findings = []
        for template in templates:
            for name, value, node in html_attributes(template["text"]):
                if not name.startswith("hf-"):
                    continue
                allowed = format_vocabulary.get(name)
                if allowed is None or is_interpolated(value) or value in allowed:
                    continue
                findings.append(
                    finding(
                        "HC-REF004",
                        f'attribute {name}="{value}" names no member of honest-format\'s '
                        "declared vocabulary. Fix the value, or extend the vocabulary.",
                        template["path"],
                        node,
                    )
                )
        return findings

    # ---- HC002 first-link half: a chain's first link accepts the boundary vocabulary its
    #      route's templates send (§497) ----

    def call_keywords(call_node):
        """Each keyword argument of a call, as {name: value_node}. A positional argument carries
        no name here and is left out."""
        arguments = call_node.child_by_field_name("arguments")
        keywords = {}
        if arguments is None:
            return keywords
        for argument in arguments.named_children:
            if argument.type != "keyword_argument":
                continue
            name = argument.child_by_field_name("name")
            value = argument.child_by_field_name("value")
            if name is not None and value is not None:
                keywords[name.text.decode("utf-8")] = value
        return keywords

    def vocabulary_base_names(vocab_call):
        """The base-type names a `vocabulary({...})` call declares: the string keys of its first
        argument's dict literal. A call whose first argument is not a dict literal declares no
        names here."""
        arguments = vocab_call.child_by_field_name("arguments")
        first = next((a for a in arguments.named_children), None) if arguments else None
        names = set()
        if first is None or first.type != "dictionary":
            return names
        for pair in first.named_children:
            if pair.type != "pair":
                continue
            key = pair.child_by_field_name("key")
            if key is not None and key.type == "string":
                names.add(py_string_value(key))
        return names

    def code_declarations():
        """Read, across every code file, the three bindings the first-link check joins: each
        chain's first link name, each link's accepts vocabulary and whether it is a boundary
        link, and each vocabulary's base-type names. Returns (chain_first, link_accepts,
        link_is_boundary, vocab_names, chain_site)."""
        chain_first = {}
        link_accepts = {}
        link_is_boundary = set()
        vocab_names = {}
        chain_site = {}
        for code in code_sources:
            root = root_under(code["text"], "python")
            for node in walk(root):
                if node.type == "assignment":
                    left = node.child_by_field_name("left")
                    right = node.child_by_field_name("right")
                    if (
                        left is not None
                        and left.type == "identifier"
                        and right is not None
                        and right.type == "call"
                    ):
                        fn = right.child_by_field_name("function")
                        if fn is not None and fn.type == "identifier":
                            bound = left.text.decode("utf-8")
                            called = fn.text.decode("utf-8")
                            if called == "chain":
                                arguments = right.child_by_field_name("arguments")
                                first = next(
                                    (a for a in arguments.named_children if a.type == "identifier"),
                                    None,
                                ) if arguments else None
                                if first is not None:
                                    chain_first[bound] = first.text.decode("utf-8")
                                    chain_site[bound] = (code["path"], right)
                            elif called == "vocabulary":
                                vocab_names[bound] = vocabulary_base_names(right)
                elif node.type == "decorated_definition":
                    definition = node.child_by_field_name("definition")
                    if definition is None or definition.type != "function_definition":
                        continue
                    name_node = definition.child_by_field_name("name")
                    if name_node is None:
                        continue
                    link = name_node.text.decode("utf-8")
                    for decorator in node.named_children:
                        if decorator.type != "decorator":
                            continue
                        expression = next(
                            (c for c in decorator.named_children), None
                        )
                        if expression is None or expression.type != "call":
                            continue
                        head = expression.child_by_field_name("function")
                        if head is None or head.type != "identifier" or head.text.decode("utf-8") != "link":
                            continue
                        keywords = call_keywords(expression)
                        if "accepts" in keywords and keywords["accepts"].type == "identifier":
                            link_accepts[link] = keywords["accepts"].text.decode("utf-8")
                        if "boundary" in keywords and keywords["boundary"].type == "true":
                            link_is_boundary.add(link)
        return chain_first, link_accepts, link_is_boundary, vocab_names, chain_site

    def object_node_keys(object_node):
        """The static keys of one JavaScript object literal: a string key's value and a bare
        identifier key's name. A computed or spread key contributes nothing."""
        keys = set()
        for member in object_node.named_children:
            if member.type != "pair":
                continue
            key = member.child_by_field_name("key")
            if key is None:
                continue
            if key.type == "string":
                keys.add(js_string_value(key))
            elif key.type == "property_identifier":
                keys.add(key.text.decode("utf-8"))
        return keys

    def manifest_keys(text):
        """The field names a template's `appManifest` declares (honest-page §5). domx sends the
        collected manifest to the server as `_state`, so each key is a field the first link can
        receive. The keys are read from a `const appManifest = {...}` object literal in a
        `<script>` the template carries."""
        keys = set()
        for body in re.findall(r"<script[^>]*>(.*?)</script>", text, re.DOTALL):
            for node in walk(root_under(body, "javascript")):
                if node.type != "variable_declarator":
                    continue
                name = node.child_by_field_name("name")
                value = node.child_by_field_name("value")
                if name is None or name.text.decode("utf-8") != "appManifest":
                    continue
                if value is not None and value.type == "object":
                    keys |= object_node_keys(value)
        return keys

    def boundary_fields(method, path):
        """The field names a route's templates send, plus a flag for a field whose name is a
        dynamic expression (§497). A template sends the route's fields when it carries an action
        (hx-get/hx-post) whose method and normalized path match the route. From such a template
        the check takes every `name` attribute value, every static `hx-vals` key, and every
        `appManifest` key, and adds the route path's own parameters. A `name` whose value
        interpolates is not statically resolvable, so the boundary is unknowable there."""
        fields = set()
        unknowable = False
        for parameter in re.findall(r"\{([^}]*)\}", path):
            if parameter:
                fields.add(parameter)
        for template in templates:
            attributes = html_attributes(template["text"])
            targets_route = any(
                _ACTION_ATTRS.get(name) == method
                and not is_dynamic_path(value)
                and normalize_path(value) == normalize_path(path)
                for name, value, _node in attributes
            )
            if not targets_route:
                continue
            for name, value, _node in attributes:
                if name == "name":
                    if is_interpolated(value):
                        unknowable = True
                    else:
                        fields.add(value)
                elif name == "hx-vals" and not is_interpolated(value):
                    for node in walk(root_under("(" + value + ")", "javascript")):
                        if node.type == "object":
                            fields |= object_node_keys(node)
            fields |= manifest_keys(template["text"])
        return fields, unknowable

    def check_hc002_boundary():
        routes = []
        for code in code_sources:
            for node in walk(root_under(code["text"], "python")):
                if node.type != "function_definition":
                    continue
                name_node = node.child_by_field_name("name")
                if name_node is None or name_node.text.decode("utf-8") != "route_table":
                    continue
                for literal in walk(node):
                    if literal.type != "dictionary":
                        continue
                    entry = {}
                    for pair in literal.named_children:
                        if pair.type != "pair":
                            continue
                        key = pair.child_by_field_name("key")
                        value = pair.child_by_field_name("value")
                        if key is None or value is None or key.type != "string" or value.type != "string":
                            continue
                        entry[py_string_value(key)] = py_string_value(value)
                    if "method" in entry and "path" in entry and "chain" in entry:
                        routes.append((entry["method"].upper(), entry["path"], entry["chain"]))
        if not routes:
            return []
        chain_first, link_accepts, link_is_boundary, vocab_names, chain_site = code_declarations()
        findings = []
        for method, path, chain_name in routes:
            if chain_name not in chain_first:
                continue
            first_link = chain_first[chain_name]
            if first_link in link_is_boundary:
                continue
            if first_link not in link_accepts:
                continue
            accepts_vocab = link_accepts[first_link]
            accepts = vocab_names[accepts_vocab] if accepts_vocab in vocab_names else set()
            fields, unknowable = boundary_fields(method, path)
            site_path, site_node = chain_site[chain_name]
            if unknowable:
                findings.append(
                    finding(
                        "HC002",
                        f"the chain for {method} {path} reads its boundary from a template "
                        "field whose name is a dynamic expression, so the boundary is not "
                        "knowable before the code runs. Give the field a static name.",
                        site_path,
                        site_node,
                    )
                )
                continue
            missing = sorted(accepts - fields)
            if missing:
                findings.append(
                    finding(
                        "HC002",
                        f"the first link {first_link!r} accepts {missing}, which no template or "
                        f"route for {method} {path} sends. Change the link's accepts, or send the "
                        "fields from the template.",
                        site_path,
                        site_node,
                    )
                )
        return findings

    return (
        check_ref001()
        + check_ref002()
        + check_ref003()
        + check_ref004()
        + check_hc002_boundary()
    )


