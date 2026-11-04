"""Parse, classify, and the set-based generators (spec sections 2, 3).

Source analysis uses the shared tree-sitter parsing boundary (honest-parse); the predicate
body is then read with Python's own `ast` over the node's text, a pure deterministic walk that
reaches no world. The set generators enumerate a bounded vocabulary exhaustively and the five
adversarial neighbour classes perturb one value, all pure.
"""

import ast
from itertools import product

import honest_parse
from honest_type.recognizers import is_bounded, members

# The alphabet the length generator repeats (spec section 3.4) and the alphanumeric alphabet
# the edit-distance neighbour class draws insertions and substitutions from (spec section 3.5).
_LENGTH_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
_EDIT_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

# Builtins a recognizer may call without the call making it composite or external (spec section 2):
# int/float/len decide numeric and length classes before this check runs, the rest are ordinary.
_BUILTINS = frozenset({
    "len", "int", "float", "str", "bool", "isinstance", "abs", "ord", "chr", "min", "max",
    "sum", "any", "all", "sorted", "list", "dict", "set", "tuple", "range", "print", "type",
    "repr", "hex", "bin", "format", "bytes", "frozenset",
})

# One confusable per ASCII letter — the curated UTS-39 subset the reference exercises (spec section
# 3.5). Each substitute is from a different Unicode block, so every neighbour carries a non-ASCII
# codepoint. Digits are absent on purpose, so an all-digit value has no confusable neighbour.
_CONFUSABLES = {
    "a": "а", "c": "с", "d": "ԁ", "e": "е", "g": "ɡ", "h": "һ", "i": "і", "j": "ј",
    "l": "ӏ", "m": "м", "n": "ո", "o": "о", "p": "р", "q": "ԛ", "s": "ѕ", "t": "т",
    "u": "ս", "v": "ѵ", "w": "ԝ", "x": "х", "y": "у", "z": "ᴢ",
}

# The control / zero-width / bidi injection set (spec section 3.5): every C0 control, DEL, every C1
# control (so U+0085 NEL is included), and the zero-width and bidirectional-override format
# characters. Each is category Cc or Cf, so every neighbour it forms carries a special codepoint.
_CONTROL_INJECTION = (
    [chr(code) for code in range(0x00, 0x20)]
    + ["\x7f"]
    + [chr(code) for code in range(0x80, 0xA0)]
    + ["​", "‎", "‏", "‪", "‫", "‬", "‭", "‮", "﻿"]
)


def parse_source(source):
    """Parse one Python source file with tree-sitter and return the tree's root node (spec
    sections 2, 9.6). Deterministic, reads no world. tree-sitter produces error nodes for
    malformed input rather than failing, so this returns a node, never a fault."""
    tree = honest_parse.parse(source.encode("utf-8"), "python")
    return tree.root_node


def _lambda_expressions(root):
    """Every lambda expression node in the tree (not the bare `lambda` keyword token, which
    carries the same type but no children)."""
    return [node for node in honest_parse.walk(root) if node.type == "lambda" and node.children]


def _recognizer_defs(root):
    """Every function_definition decorated with @recognizer (spec section 2)."""
    out = []
    for node in honest_parse.walk(root):
        if node.type != "decorated_definition":
            continue
        decorators = [child for child in node.children if child.type == "decorator"]
        if any("recognizer" in decorator.text.decode("utf-8") for decorator in decorators):
            for child in node.children:
                if child.type == "function_definition":
                    out.append(child)
    return out


def extract_predicates(tree):
    """Walk a parsed tree and return each recognizer predicate node (spec section 2): every
    lambda expression and every @recognizer-decorated function. The empty list means the file
    declares no predicate. Reads no world, returns pure data."""
    return _lambda_expressions(tree) + _recognizer_defs(tree)


def _node_ast(node):
    """The predicate node's source parsed with Python's ast (a lambda expression or a def)."""
    return ast.parse(node.text.decode("utf-8"))


def _root(node):
    """The tree's root, reached by walking parents — so classify can read the whole module."""
    current = node
    while current.parent is not None:
        current = current.parent
    return current


def _defined_names(node):
    """Every name the module defines — function names and module-level assignments — read from
    the whole source so a call can be told composite (defined here) from external (not)."""
    module = ast.parse(_root(node).text.decode("utf-8"))
    names = set()
    for item in ast.walk(module):
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(item.name)
        elif isinstance(item, ast.Assign):
            names.update(target.id for target in item.targets if isinstance(target, ast.Name))
    return names


def _calls(tree):
    """Every ast.Call in a predicate body."""
    return [item for item in ast.walk(tree) if isinstance(item, ast.Call)]


def _calls_named(tree, names):
    """True when the body calls a bare function whose name is in `names`."""
    for call in _calls(tree):
        if isinstance(call.func, ast.Name) and call.func.id in names:
            return True
    return False


def _calls_method(tree, methods):
    """True when the body calls a method `.m()` with m in `methods`."""
    for call in _calls(tree):
        if isinstance(call.func, ast.Attribute) and call.func.attr in methods:
            return True
    return False


def _has_numeric_literal_comparison(tree):
    """True when a comparison in the body has a numeric literal operand."""
    for item in ast.walk(tree):
        if isinstance(item, ast.Compare):
            operands = [item.left, *item.comparators]
            if any(isinstance(o, ast.Constant) and isinstance(o.value, (int, float)) and not isinstance(o.value, bool) for o in operands):
                return True
    return False


def _user_call_name(tree):
    """The first bare-identifier call that is not a builtin, or None."""
    for call in _calls(tree):
        if isinstance(call.func, ast.Name) and call.func.id not in _BUILTINS:
            return call.func.id
    return None


def classify_predicate(predicate_node):
    """Sort one predicate into its generation class by analyzing its AST (spec section 2). Reads
    no world, returns exactly one PredicateClass."""
    body = _node_ast(predicate_node)
    if _calls_named(body, {"len"}):
        return "length_bounded"
    if _calls_method(body, {"isdigit", "isalpha", "isupper"}):
        return "character_class"
    if _calls_named(body, {"int", "float"}) or _has_numeric_literal_comparison(body):
        return "numeric"
    called = _user_call_name(body)
    if called is not None:
        return "composite" if called in _defined_names(predicate_node) else "external_lookup"
    return "catch_all"


def _string_of_length(length):
    """A length-`length` string by repeating the length alphabet (spec section 3.4)."""
    repeats = (length // len(_LENGTH_ALPHABET)) + 1
    return (_LENGTH_ALPHABET * repeats)[:length]


def _len_comparison(body):
    """The (min, max) a len() comparison bounds, read from the operators the AST holds (spec
    section 3.4). max is None when the predicate is unbounded above (a pure lower bound)."""
    for item in ast.walk(body):
        if not isinstance(item, ast.Compare):
            continue
        operands = [item.left, *item.comparators]
        length_index = next(
            (index for index, operand in enumerate(operands)
             if isinstance(operand, ast.Call) and isinstance(operand.func, ast.Name) and operand.func.id == "len"),
            None,
        )
        if length_index is None:
            continue
        minimum, maximum = 1, None
        if length_index > 0:
            lower = operands[length_index - 1]
            operator = item.ops[length_index - 1]
            if isinstance(lower, ast.Constant):
                minimum, maximum = _lower_bound(type(operator).__name__, lower.value, minimum, maximum)
        if length_index < len(operands) - 1:
            upper = operands[length_index + 1]
            operator = item.ops[length_index]
            if isinstance(upper, ast.Constant):
                minimum, maximum = _upper_bound(type(operator).__name__, upper.value, minimum, maximum)
        return minimum, maximum
    return 1, None


def _lower_bound(operator_name, value, minimum, maximum):
    """Resolve a `literal OP len` clause into (min, max)."""
    table = {
        "LtE": (value, maximum),
        "Lt": (value + 1, maximum),
        "Eq": (value, value),
        "GtE": (minimum, value),
        "Gt": (minimum, value - 1),
    }
    return table.get(operator_name, (minimum, maximum))


def _upper_bound(operator_name, value, minimum, maximum):
    """Resolve a `len OP literal` clause into (min, max)."""
    table = {
        "LtE": (minimum, value),
        "Lt": (minimum, value - 1),
        "Eq": (value, value),
        "GtE": (value, maximum),
        "Gt": (value + 1, maximum),
    }
    return table.get(operator_name, (minimum, maximum))


def enumerate_lengths(predicate_node):
    """Generate the strings for a length-bounded predicate (spec section 3.4): one valid string
    at every in-range length, plus the boundary lengths just outside. An unbounded predicate
    generates nothing here and falls to supplied values. Reads no world, returns pure data."""
    minimum, maximum = _len_comparison(_node_ast(predicate_node))
    if maximum is None:
        return {"valid": [], "invalid": []}
    valid = [_string_of_length(length) for length in range(minimum, maximum + 1)]
    invalid = [_string_of_length(maximum + 1)]
    if minimum > 1:
        invalid.append(_string_of_length(minimum - 1))
    return {"valid": valid, "invalid": invalid}


def fibonacci_sequence(limit, negative):
    """The numeric probe values from zero up to limit (spec section 3.3): logarithmically
    distributed, probing a range rather than enumerating it. The negatives are prepended in
    number-line order when negative is true. Reads no world, returns pure data."""
    sequence = [0, 1]
    while sequence[-1] <= limit:
        sequence.append(sequence[-2] + sequence[-1])
    positive = [value for value in sequence if value <= limit]
    if negative:
        negatives = sorted(-value for value in positive if value > 0)
        return negatives + positive
    return positive


def supplied_cases(predicate_name, supplied_values):
    """Resolve one predicate's programmer-supplied values from the config the reader handed in
    (spec section 3.6). missing is true with empty lists when the config has no entry — the case
    the runner turns into a warning. Reads no file, returns pure data."""
    if predicate_name in supplied_values:
        entry = supplied_values[predicate_name]
        return {"valid": list(entry["valid"]), "invalid": list(entry["invalid"]), "missing": False}
    return {"valid": [], "invalid": [], "missing": True}


def _set_members(vocab):
    """The bounded recognizers of a vocabulary as {type_name: sorted members}, in declaration
    order; predicate recognizers contribute no entry (spec section 3.2)."""
    out = {}
    for name, recognizer in vocab["base_types"].items():
        if is_bounded(recognizer):
            out[name] = sorted(members(recognizer))
    return out


def enumerate_sets(vocab):
    """Generate every test case for a Set-based vocabulary (spec section 3.2): the Cartesian
    product of every Set member, no sampling, one manifest per combination. A vocabulary of only
    predicate recognizers yields one empty manifest. Reads no world, returns pure data."""
    set_types = _set_members(vocab)
    if not set_types:
        return [{}]
    names = list(set_types)
    return [dict(zip(names, combination)) for combination in product(*(set_types[name] for name in names))]


def enumerate_test_cases(accepts, binding):
    """Build the input manifests a link accepts (spec section 4.6): enumerate the vocabulary the
    way enumerate_sets does, then rekey each manifest by the binding's slot names. Reads no
    world, returns pure data."""
    return [
        {binding.get(type_name, type_name): value for type_name, value in manifest.items()}
        for manifest in enumerate_sets(accepts)
    ]


def edit_distance_1(value):
    """The edit-distance-1 neighbour class (spec section 3.5): every deletion, every
    alphanumeric insertion, every substitution, the case variants and the whitespace variants,
    with the identity removed. Reads no world, returns pure data."""
    characters = list(value)
    results = []
    for index in range(len(characters)):
        results.append("".join(characters[:index] + characters[index + 1:]))
    for index in range(len(characters) + 1):
        for character in _EDIT_ALPHABET:
            results.append("".join(characters[:index] + [character] + characters[index:]))
    for index in range(len(characters)):
        for character in _EDIT_ALPHABET:
            if character != characters[index]:
                results.append("".join(characters[:index] + [character] + characters[index + 1:]))
    results.extend([value.lower(), value.upper(), value.title()])
    results.extend([" " + value, value + " "])
    if len(value) >= 2:
        results.append(value[0] + " " + value[1:])
    return [neighbor for neighbor in results if neighbor != value]


def unicode_confusables(value):
    """The Unicode-confusable neighbour class (spec section 3.5): each confusable ASCII character
    substituted one at a time, plus one full-homoglyph neighbour substituting every replaceable
    character at once. A value with no confusable character yields nothing. Reads no world."""
    results = []
    for index, character in enumerate(value):
        if character in _CONFUSABLES:
            results.append(value[:index] + _CONFUSABLES[character] + value[index + 1:])
    replaceable = [character for character in value if character in _CONFUSABLES]
    if len(replaceable) >= 2:
        results.append("".join(_CONFUSABLES.get(character, character) for character in value))
    return [neighbor for neighbor in dict.fromkeys(results) if neighbor != value]


def control_characters(value):
    """The control-character neighbour class (spec section 3.5): each injection character
    prepended, appended, and inserted at the midpoint of value. Reads no world."""
    midpoint = len(value) // 2
    results = []
    for character in _CONTROL_INJECTION:
        results.append(character + value)
        results.append(value + character)
        results.append(value[:midpoint] + character + value[midpoint:])
    return results


def length_extensions(value):
    """The length-extension neighbour class (spec section 3.5): value repeated 10, 100 and 1000
    times, then padded across the uint16 boundary and toward one megabyte. Reads no world."""
    return [
        value * 10,
        value * 100,
        value * 1000,
        value + ("A" * 65535),
        value + ("A" * 65536),
        value + ("A" * 1048575),
    ]


def _percent_encode(text):
    """Percent-encode every non-alphanumeric character, so a double application yields %25xx."""
    return "".join(character if character.isalnum() else "%%%02X" % ord(character) for character in text)


def _overlong_utf8(value):
    """The str form of an overlong two-byte UTF-8 encoding of each ASCII character (spec section
    3.5): a byte sequence a strict decoder must reject, carried here as its latin-1 string."""
    return "".join(chr(0xC0 | (ord(character) >> 6)) + chr(0x80 | (ord(character) & 0x3F)) for character in value)


def encoding_variants(value):
    """The encoding-variant neighbour class (spec section 3.5): a UTF-16 BOM prefix, an overlong
    UTF-8 encoding, a double percent-encoding, and — when the value has a space — the
    whitespace-normalization attacks. Reads no world."""
    results = [
        "﻿" + value,
        _overlong_utf8(value),
        _percent_encode(_percent_encode(value)),
    ]
    if " " in value:
        results.append(value.replace(" ", "\xa0"))
        results.append(value.replace(" ", " "))
    return [neighbor for neighbor in dict.fromkeys(results) if neighbor != value]


def adversarial_neighbors(value):
    """The deduplicated union of the five adversarial neighbour classes with the original value
    removed (spec section 3.5). Reads no world, returns pure data."""
    combined = (
        edit_distance_1(value)
        + unicode_confusables(value)
        + control_characters(value)
        + length_extensions(value)
        + encoding_variants(value)
    )
    return [neighbor for neighbor in dict.fromkeys(combined) if neighbor != value]
