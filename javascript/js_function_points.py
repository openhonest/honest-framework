"""List the function points of JavaScript source: the named functions the feature gate binds one
gherkin scenario to each. A function point is a named function — a `function`/`function*` declaration,
or a `const`/`let`/`var` bound to an arrow or function expression. Anonymous functions (the extractors
inside a dispatch table, a callback literal) are not points: there is no name to bind a scenario to,
and they are exercised through the named function that returns or holds them.

This is harness tooling (the JavaScript counterpart of feature-gate.sh's `grep def`), run through the
python workspace for the shared tree-sitter boundary. Not itself under the honest-check gate.

  cd python && uv run python ../javascript/js_function_points.py <file.js> [<file.js> ...]
"""

import sys

from honest_parse import node_text, parse_javascript, walk

_FUNCTION_VALUES = ("arrow_function", "function_expression", "generator_function")
_FUNCTION_DECLARATIONS = ("function_declaration", "generator_function_declaration")


def function_points(source):
    root = parse_javascript(source.encode("utf-8")).root_node
    names = []
    for node in walk(root):
        if node.type in _FUNCTION_DECLARATIONS:
            name = node.child_by_field_name("name")
            if name is not None:
                names.append(node_text(name, source.encode("utf-8")))
        elif node.type in ("lexical_declaration", "variable_declaration"):
            for declarator in node.named_children:
                value = declarator.child_by_field_name("value")
                name = declarator.child_by_field_name("name")
                if value is not None and value.type in _FUNCTION_VALUES and name is not None and name.type == "identifier":
                    names.append(node_text(name, source.encode("utf-8")))
    return names


def main(paths):
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            for name in function_points(handle.read()):
                print(name)


if __name__ == "__main__":
    main(sys.argv[1:])
