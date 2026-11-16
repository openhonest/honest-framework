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

from honest_test._util import _choose, _pick, _read_or

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
    return list(filter(lambda node: node.type == "lambda" and node.children, honest_parse.walk(root)))


def _has_recognizer_decorator(node):
    """True when a decorated_definition carries an @recognizer decorator (spec section 2)."""
    decorators = filter(lambda child: child.type == "decorator", node.children)
    return any("recognizer" in decorator.text.decode("utf-8") for decorator in decorators)


def _function_defs_of(node):
    """The function_definition children of a decorated_definition (spec section 2)."""
    return list(filter(lambda child: child.type == "function_definition", node.children))


def _recognizer_defs(root):
    """Every function_definition decorated with @recognizer (spec section 2)."""
    out = []
    decorated = filter(lambda node: node.type == "decorated_definition", honest_parse.walk(root))
    for node in decorated:
        _pick(
            _has_recognizer_decorator(node),
            lambda: out.extend(_function_defs_of(node)),
            lambda: None,
        )
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


def _func_name(item):
    """The function name a FunctionDef or AsyncFunctionDef defines (spec section 2)."""
    return {item.name}


def _assign_names(item):
    """The module-level names an assignment binds (spec section 2)."""
    targets = filter(lambda target: isinstance(target, ast.Name), item.targets)
    return set(target.id for target in targets)


_NAME_EXTRACTORS = {
    ast.FunctionDef: _func_name,
    ast.AsyncFunctionDef: _func_name,
    ast.Assign: _assign_names,
}


def _names_of(item):
    """The names one AST node defines (spec section 2): function names and assignment targets, the
    empty set for any other node."""
    extractor = _read_or(_NAME_EXTRACTORS, type(item), None)
    return _pick(extractor is None, lambda: set(), lambda: extractor(item))


def _defined_names(node):
    """Every name the module defines — function names and module-level assignments — read from
    the whole source so a call can be told composite (defined here) from external (not)."""
    module = ast.parse(_root(node).text.decode("utf-8"))
    names = set()
    for item in ast.walk(module):
        names.update(_names_of(item))
    return names


def _calls(tree):
    """Every ast.Call in a predicate body."""
    return list(filter(lambda item: isinstance(item, ast.Call), ast.walk(tree)))


def _calls_named(tree, names):
    """True when the body calls a bare function whose name is in `names`."""
    return any(isinstance(call.func, ast.Name) and call.func.id in names for call in _calls(tree))


def _calls_method(tree, methods):
    """True when the body calls a method `.m()` with m in `methods`."""
    return any(isinstance(call.func, ast.Attribute) and call.func.attr in methods for call in _calls(tree))


def _compare_has_numeric(item):
    """True when a comparison node has a numeric (non-bool) literal operand (spec section 2)."""
    operands = [item.left, *item.comparators]
    return any(
        isinstance(o, ast.Constant) and isinstance(o.value, (int, float)) and not isinstance(o.value, bool)
        for o in operands
    )


def _has_numeric_literal_comparison(tree):
    """True when a comparison in the body has a numeric literal operand."""
    compares = filter(lambda item: isinstance(item, ast.Compare), ast.walk(tree))
    return any(_compare_has_numeric(item) for item in compares)


def _user_call_name(tree):
    """The first bare-identifier call that is not a builtin, or None."""
    user_calls = filter(
        lambda call: isinstance(call.func, ast.Name) and call.func.id not in _BUILTINS,
        _calls(tree),
    )
    for call in user_calls:
        return call.func.id
    return None


def _classify_composite(predicate_node, called):
    """A user call resolves to composite when the module defines it, external_lookup otherwise
    (spec section 2)."""
    return _choose(called in _defined_names(predicate_node), "composite", "external_lookup")


def _classify_user_or_catch(predicate_node, body):
    """A predicate with no earlier class is composite/external when it calls a user function,
    catch_all when it calls none (spec section 2)."""
    called = _user_call_name(body)
    return _pick(
        called is None,
        lambda: "catch_all",
        lambda: _classify_composite(predicate_node, called),
    )


def _classify_not_character(predicate_node, body):
    """Classify a predicate that is neither length-bounded nor character-class (spec section 2):
    numeric when it calls int/float or compares a numeric literal, else the user-call classes."""
    return _pick(
        _calls_named(body, {"int", "float"}) or _has_numeric_literal_comparison(body),
        lambda: "numeric",
        lambda: _classify_user_or_catch(predicate_node, body),
    )


def _classify_not_length(predicate_node, body):
    """Classify a predicate that is not length-bounded (spec section 2): character_class when it
    calls a string predicate method, else on to the numeric and user-call classes."""
    return _pick(
        _calls_method(body, {"isdigit", "isalpha", "isupper"}),
        lambda: "character_class",
        lambda: _classify_not_character(predicate_node, body),
    )


def classify_predicate(predicate_node):
    """Sort one predicate into its generation class by analyzing its AST (spec section 2). Reads
    no world, returns exactly one PredicateClass."""
    body = _node_ast(predicate_node)
    return _pick(
        _calls_named(body, {"len"}),
        lambda: "length_bounded",
        lambda: _classify_not_length(predicate_node, body),
    )


def _string_of_length(length):
    """A length-`length` string by repeating the length alphabet (spec section 3.4)."""
    repeats = (length // len(_LENGTH_ALPHABET)) + 1
    return (_LENGTH_ALPHABET * repeats)[:length]


def _length_index(item):
    """The operand index of the len() call in a comparison, or None when it has no len() operand
    (spec section 3.4)."""
    operands = [item.left, *item.comparators]
    indexed = filter(
        lambda io: isinstance(io[1], ast.Call) and isinstance(io[1].func, ast.Name) and io[1].func.id == "len",
        enumerate(operands),
    )
    first = next(indexed, None)
    return _pick(first is None, lambda: None, lambda: first[0])


def _has_len_operand(item):
    """True when a comparison has a len() call operand (spec section 3.4)."""
    return _length_index(item) is not None


def _lower_from_operand(lower, operator, current):
    """Fold a `literal OP len` clause into the running (min, max) when the literal is a constant
    (spec section 3.4)."""
    minimum, maximum = current
    return _pick(
        isinstance(lower, ast.Constant),
        lambda: _lower_bound(type(operator).__name__, lower.value, minimum, maximum),
        lambda: current,
    )


def _apply_lower(operands, ops, length_index, current):
    """Apply the lower clause of a len comparison when one sits left of the len() operand (spec
    section 3.4)."""
    return _pick(
        length_index > 0,
        lambda: _lower_from_operand(operands[length_index - 1], ops[length_index - 1], current),
        lambda: current,
    )


def _upper_from_operand(upper, operator, current):
    """Fold a `len OP literal` clause into the running (min, max) when the literal is a constant
    (spec section 3.4)."""
    minimum, maximum = current
    return _pick(
        isinstance(upper, ast.Constant),
        lambda: _upper_bound(type(operator).__name__, upper.value, minimum, maximum),
        lambda: current,
    )


def _apply_upper(operands, ops, length_index, current):
    """Apply the upper clause of a len comparison when one sits right of the len() operand (spec
    section 3.4)."""
    return _pick(
        length_index < len(operands) - 1,
        lambda: _upper_from_operand(operands[length_index + 1], ops[length_index], current),
        lambda: current,
    )


def _compare_bounds(item):
    """The (min, max) a single len() comparison bounds (spec section 3.4)."""
    operands = [item.left, *item.comparators]
    length_index = _length_index(item)
    after_lower = _apply_lower(operands, item.ops, length_index, (1, None))
    return _apply_upper(operands, item.ops, length_index, after_lower)


def _len_comparison(body):
    """The (min, max) a len() comparison bounds, read from the operators the AST holds (spec
    section 3.4). max is None when the predicate is unbounded above (a pure lower bound)."""
    compares = filter(lambda item: isinstance(item, ast.Compare), ast.walk(body))
    with_len = filter(_has_len_operand, compares)
    for item in with_len:
        return _compare_bounds(item)
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
    return _read_or(table, operator_name, (minimum, maximum))


def _upper_bound(operator_name, value, minimum, maximum):
    """Resolve a `len OP literal` clause into (min, max)."""
    table = {
        "LtE": (minimum, value),
        "Lt": (minimum, value - 1),
        "Eq": (value, value),
        "GtE": (value, maximum),
        "Gt": (value + 1, maximum),
    }
    return _read_or(table, operator_name, (minimum, maximum))


def _bounded_lengths(minimum, maximum):
    """The valid and invalid strings for a length-bounded predicate with a finite maximum (spec
    section 3.4)."""
    valid = [_string_of_length(length) for length in range(minimum, maximum + 1)]
    invalid = [_string_of_length(maximum + 1)] + _pick(
        minimum > 1,
        lambda: [_string_of_length(minimum - 1)],
        lambda: [],
    )
    return {"valid": valid, "invalid": invalid}


def enumerate_lengths(predicate_node):
    """Generate the strings for a length-bounded predicate (spec section 3.4): one valid string
    at every in-range length, plus the boundary lengths just outside. An unbounded predicate
    generates nothing here and falls to supplied values. Reads no world, returns pure data."""
    minimum, maximum = _len_comparison(_node_ast(predicate_node))
    return _pick(
        maximum is None,
        lambda: {"valid": [], "invalid": []},
        lambda: _bounded_lengths(minimum, maximum),
    )


def _with_negatives(positive):
    """The negatives prepended to the positive probe values in number-line order (spec section
    3.3)."""
    negatives = sorted(-value for value in filter(lambda value: value > 0, positive))
    return negatives + positive


def fibonacci_sequence(limit, negative):
    """The numeric probe values from zero up to limit (spec section 3.3): logarithmically
    distributed, probing a range rather than enumerating it. The negatives are prepended in
    number-line order when negative is true. Reads no world, returns pure data."""
    sequence = [0, 1]
    while sequence[-1] <= limit:
        sequence.append(sequence[-2] + sequence[-1])
    positive = list(filter(lambda value: value <= limit, sequence))
    return _pick(negative, lambda: _with_negatives(positive), lambda: positive)


def _supplied_entry(entry):
    """One predicate's supplied valid and invalid values from its config entry (spec section 3.6)."""
    return {"valid": list(entry["valid"]), "invalid": list(entry["invalid"]), "missing": False}


def supplied_cases(predicate_name, supplied_values):
    """Resolve one predicate's programmer-supplied values from the config the reader handed in
    (spec section 3.6). missing is true with empty lists when the config has no entry — the case
    the runner turns into a warning. Reads no file, returns pure data."""
    return _pick(
        predicate_name in supplied_values,
        lambda: _supplied_entry(supplied_values[predicate_name]),
        lambda: {"valid": [], "invalid": [], "missing": True},
    )


def _set_members(vocab):
    """The bounded recognizers of a vocabulary as {type_name: sorted members}, in declaration
    order; predicate recognizers contribute no entry (spec section 3.2)."""
    out = {}
    bounded = filter(lambda nr: is_bounded(nr[1]), vocab["base_types"].items())
    for name, recognizer in bounded:
        out[name] = sorted(members(recognizer))
    return out


def _product_manifests(set_types):
    """One manifest per Cartesian-product combination of the Set members (spec section 3.2)."""
    names = list(set_types)
    return [dict(zip(names, combination)) for combination in product(*(set_types[name] for name in names))]


def enumerate_sets(vocab):
    """Generate every test case for a Set-based vocabulary (spec section 3.2): the Cartesian
    product of every Set member, no sampling, one manifest per combination. A vocabulary of only
    predicate recognizers yields one empty manifest. Reads no world, returns pure data."""
    set_types = _set_members(vocab)
    return _pick(bool(set_types), lambda: _product_manifests(set_types), lambda: [{}])


def enumerate_test_cases(accepts, binding):
    """Build the input manifests a link accepts (spec section 4.6): enumerate the vocabulary the
    way enumerate_sets does, then rekey each manifest by the binding's slot names. Reads no
    world, returns pure data."""
    return [
        {_read_or(binding, type_name, type_name): value for type_name, value in manifest.items()}
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
        for character in filter(lambda c: c != characters[index], _EDIT_ALPHABET):
            results.append("".join(characters[:index] + [character] + characters[index + 1:]))
    results.extend([value.lower(), value.upper(), value.title()])
    results.extend([" " + value, value + " "])
    _pick(
        len(value) >= 2,
        lambda: results.append(value[0] + " " + value[1:]),
        lambda: None,
    )
    return list(filter(lambda neighbor: neighbor != value, results))


def unicode_confusables(value):
    """The Unicode-confusable neighbour class (spec section 3.5): each confusable ASCII character
    substituted one at a time, plus one full-homoglyph neighbour substituting every replaceable
    character at once. A value with no confusable character yields nothing. Reads no world."""
    confusable_positions = filter(lambda ic: ic[1] in _CONFUSABLES, enumerate(value))
    singles = [value[:index] + _read_or(_CONFUSABLES, character, character) + value[index + 1:]
               for index, character in confusable_positions]
    replaceable = list(filter(lambda character: character in _CONFUSABLES, value))
    full = _pick(
        len(replaceable) >= 2,
        lambda: ["".join(_read_or(_CONFUSABLES, character, character) for character in value)],
        lambda: [],
    )
    return list(filter(lambda neighbor: neighbor != value, dict.fromkeys(singles + full)))


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
    return "".join(_choose(character.isalnum(), character, "%%%02X" % ord(character)) for character in text)


def _overlong_utf8(value):
    """The str form of an overlong two-byte UTF-8 encoding of each ASCII character (spec section
    3.5): a byte sequence a strict decoder must reject, carried here as its latin-1 string."""
    return "".join(chr(0xC0 | (ord(character) >> 6)) + chr(0x80 | (ord(character) & 0x3F)) for character in value)


def encoding_variants(value):
    """The encoding-variant neighbour class (spec section 3.5): a UTF-16 BOM prefix, an overlong
    UTF-8 encoding, a double percent-encoding, and — when the value has a space — the
    whitespace-normalization attacks. Reads no world."""
    base = [
        "﻿" + value,
        _overlong_utf8(value),
        _percent_encode(_percent_encode(value)),
    ]
    results = base + _pick(
        " " in value,
        lambda: [value.replace(" ", "\xa0"), value.replace(" ", " ")],
        lambda: [],
    )
    return list(filter(lambda neighbor: neighbor != value, dict.fromkeys(results)))


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
    return list(filter(lambda neighbor: neighbor != value, dict.fromkeys(combined)))
