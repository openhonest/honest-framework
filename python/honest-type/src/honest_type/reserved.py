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


RESERVED_FIELDS = frozenset({"is_err"})
"""Field names no record but a Fault may declare (section 13.2).

This is a different reservation from RESERVED_WORDS above, and the two must not be merged.
RESERVED_WORDS forbids a token as a *vocabulary Set member*, so a user's word cannot collide with a
framework noun. RESERVED_FIELDS forbids a name as a *field of a declared record*, so the Fault
recognizer's tag cannot appear on a success value. Putting `is_err` in Layer 1 would forbid the
wrong thing: a vocabulary member spelled "is_err", which nobody wants and which was never the risk.
"""


def is_reserved(token: str) -> bool:
    return token in RESERVED_WORDS


def is_reserved_field(name: str) -> bool:
    """True when `name` is a field only a Fault may declare (section 13.2). honest-check enforces the
    reservation statically over `.hd` record declarations; this is the one list both it and a runtime
    caller read, so the reservation cannot drift between them."""
    return name in RESERVED_FIELDS


def reservation_layer(token: str):
    """The name of the layer that reserves `token`, or None if it is not reserved."""
    for layer_name, words in filter(lambda item: token in item[1], _LAYERS.items()):
        return layer_name
    return None
