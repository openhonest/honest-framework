"""honest-check the whole-set cross-file reference core (HC-REF002, HC-REF003), split from core.py so no module is a god-file (L1.17).

The per-rule logic nests here as data exactly as it did in core.py; the exact Diagnostic each
rule produces is pinned by the conformance suite (section 9.2), not by a separately declared
function."""

import ast
from honest_parse import language_of, line_col, parse, parse_source, walk
from honest_check.constants import _CLASSLIST_METHODS, _INTERPOLATION_MARKERS, _TEMPLATE_GRAMMARS


def check_references(sources):
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

    return check_ref002() + check_ref003()


