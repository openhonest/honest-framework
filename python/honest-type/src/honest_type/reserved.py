"""Reserved words (spec §2).

Vocabulary construction must reject any Set member that collides with a
reserved word. Three layers: Layer 1 (framework structural nouns) and Layer 2
(cross-language minimum) are defined here and mandatory for every spoke;
Layer 3 is the host language's own keyword list (Python here).

Predicate recognizers cannot be checked at construction time (unbounded input
space); a predicate that matches a reserved word is caught at classify() time
with a `reserved_word` rejection (see classify.py).
"""
from __future__ import annotations

# Layer 1: Framework Reserved — honest-type's own structural nouns.
LAYER_1_FRAMEWORK: frozenset[str] = frozenset({
    "manifest", "ticket", "rejection", "fault", "vocabulary", "binding",
    "link", "chain", "recognizer", "slot", "token", "widget", "grid", "cell",
})

# Layer 2: Cross-Language Minimum — common keywords across target languages.
LAYER_2_CROSS_LANGUAGE: frozenset[str] = frozenset({
    "if", "else", "elif", "for", "while", "do", "switch", "case", "break",
    "continue", "return",
    "class", "import", "export", "from", "as", "with", "yield", "async",
    "await",
    "function", "def", "var", "let", "const", "static", "new", "delete",
    "try", "catch", "finally", "throw", "raise", "except",
    "true", "false", "null", "nil", "None", "undefined", "NaN",
    "self", "this", "super",
    "and", "or", "not", "in", "is", "typeof", "instanceof",
    "int", "float", "str", "string", "bool", "boolean", "void",
    "public", "private", "protected", "abstract", "interface", "extends",
    "implements",
    "print", "puts", "echo", "console", "require", "include", "module",
    "package",
})

# Layer 3: Language-Specific — Python keywords beyond Layer 2.
LAYER_3_PYTHON: frozenset[str] = frozenset({
    "nonlocal", "global", "lambda", "pass", "assert", "del", "exec", "eval",
})

# Layer name in priority order, for reporting which layer a word belongs to.
_LAYERS: list[tuple[str, frozenset[str]]] = [
    ("framework", LAYER_1_FRAMEWORK),
    ("cross_language", LAYER_2_CROSS_LANGUAGE),
    ("language", LAYER_3_PYTHON),
]

RESERVED_WORDS: frozenset[str] = (
    LAYER_1_FRAMEWORK | LAYER_2_CROSS_LANGUAGE | LAYER_3_PYTHON
)


def reservation_layer(word: str) -> str | None:
    """Return the layer name a word is reserved in, or None if it is free.

    First match wins (framework > cross_language > language).
    """
    for layer_name, members in _LAYERS:
        if word in members:
            return layer_name
    return None


def is_reserved(word: str) -> bool:
    return word in RESERVED_WORDS
