"""Reserved words (section 2). Three layers; vocabulary construction rejects any Set
member that collides. Layer 1 = honest-type's structural nouns; Layer 2 = cross-language
minimum; Layer 3 = this language (Python).
"""

_LAYER1 = frozenset(
    {
        "manifest", "ticket", "rejection", "fault", "vocabulary", "binding",
        "link", "chain", "recognizer", "slot", "token", "widget", "grid", "cell",
    }
)

_LAYER2 = frozenset(
    {
        "if", "else", "elif", "for", "while", "do", "switch", "case", "break",
        "continue", "return", "class", "import", "export", "from", "as", "with",
        "yield", "async", "await", "function", "def", "var", "let", "const",
        "static", "new", "delete", "try", "catch", "finally", "throw", "raise",
        "except", "true", "false", "null", "nil", "None", "undefined", "NaN",
        "self", "this", "super", "and", "or", "not", "in", "is", "typeof",
        "instanceof", "int", "float", "str", "string", "bool", "boolean", "void",
        "public", "private", "protected", "abstract", "interface", "extends",
        "implements", "print", "puts", "echo", "console", "require", "include",
        "module", "package",
    }
)

_LAYER3_PYTHON = frozenset(
    {"nonlocal", "global", "lambda", "pass", "assert", "del", "exec", "eval"}
)

RESERVED_WORDS = _LAYER1 | _LAYER2 | _LAYER3_PYTHON

# Layer lookup is a table, not a branch (section 2 / honest-code dict-dispatch).
_LAYERS = {"framework": _LAYER1, "cross-language": _LAYER2, "python": _LAYER3_PYTHON}


def is_reserved(token: str) -> bool:
    return token in RESERVED_WORDS


def reservation_layer(token: str):
    """The name of the layer that reserves `token`, or None if it is not reserved."""
    for layer_name, words in _LAYERS.items():
        if token in words:
            return layer_name
    return None
