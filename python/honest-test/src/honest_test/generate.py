"""Case generation over live declarations and the adversarial-neighbor vocabulary
(spec sections 3.2, 3.5, 4.6, 8.2). Every function is pure: it reads a validated
vocabulary or a string and returns data.
"""

from itertools import product

from honest_type.recognizers import is_bounded, members
from honest_type.vocabulary import is_maybe, unwrap_maybe

from honest_test._util import _choose, _read_or

_ALPHA = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

_CONFUSABLES = {
    "a": ["а", "ɑ", "ａ", "\U0001d41a"],
    "A": ["А", "Ａ", "\U0001d400"],
    "b": ["Ƅ", "ｂ", "\U0001d41b"],
    "c": ["с", "ｃ", "\U0001d41c"],
    "e": ["е", "ｅ", "\U0001d41e"],
    "i": ["і", "ｉ", "\U0001d422"],
    "l": ["ӏ", "ｌ", "\U0001d425"],
    "o": ["о", "ｏ", "\U0001d428"],
    "s": ["ѕ", "ｓ", "\U0001d42c"],
    "x": ["х", "ｘ", "\U0001d431"],
    "y": ["у", "ｙ", "\U0001d432"],
    "p": ["р", "ｐ", "\U0001d429"],
    "0": ["０", "\U0001d7ce"],
    "1": ["１", "\U0001d7cf"],
}

_INJECTION = [
    "\x00", "\x08", "\x09", "\x0a", "\x0d", "\x1b", "\x7f",
    "​", "‎", "‏", "‪", "‫", "‬",
    "‭", "‮", "﻿",
]


def enumerate_sets(vocab):
    """Generate the Cartesian product of every Set recognizer's members, no sampling
    (section 3.2). Each case is a manifest keyed by the type name. A predicate recognizer
    contributes no slot, so a predicate-only vocabulary enumerates to one empty manifest."""
    bounded = filter(lambda item: is_bounded(item[1]), vocab["base_types"].items())
    slots = [(name, sorted(members(rec))) for name, rec in bounded]
    names = [name for name, _ in slots]
    value_lists = [values for _, values in slots]
    return [dict(zip(names, combo)) for combo in product(*value_lists)]


def enumerate_test_cases(accepts, binding):
    """Enumerate the vocabulary the way enumerate_sets does, then name each slot through
    the binding, so each case is a ready input for the link under test (section 4.6). A
    Maybe slot adds its absent arm, binding that slot to a null value."""
    bounded = filter(lambda item: is_bounded(item[1]), accepts["base_types"].items())

    def _slot(name, rec):
        bound = _read_or(binding, name, name)
        values = sorted(members(rec))
        extra = _choose(is_maybe(bound), [None], [])
        return unwrap_maybe(bound), values + extra

    slots = [_slot(name, rec) for name, rec in bounded]
    names = [name for name, _ in slots]
    value_lists = [values for _, values in slots]
    return [dict(zip(names, combo)) for combo in product(*value_lists)]


def edit_distance_1(value):
    """The edit-distance-1 neighbor class (section 3.5): every deletion, every insertion
    from the 62-character alphanumeric alphabet, every substitution, the case variants, and
    the whitespace variants."""
    chars = list(value)
    results = []
    for i in range(len(chars)):
        results.append("".join(chars[:i] + chars[i + 1:]))
    for i in range(len(chars) + 1):
        for character in _ALPHA:
            results.append("".join(chars[:i] + [character] + chars[i:]))
    for i in range(len(chars)):
        current = chars[i]
        for character in filter(lambda c: c != current, _ALPHA):
            results.append("".join(chars[:i] + [character] + chars[i + 1:]))
    results.append(value.lower())
    results.append(value.upper())
    results.append(value.title())
    results.append(" " + value)
    results.append(value + " ")
    results.extend(_choose(len(value) >= 2, [value[0] + " " + value[1:]], []))
    return results


def unicode_confusables(value):
    """The Unicode-confusable neighbor class (section 3.5): for each character with a known
    visually-similar character, one neighbor with it substituted at that position, plus one
    full-homoglyph neighbor with every replaceable character substituted at once."""
    def _first_confusable(character):
        return _read_or(_CONFUSABLES, character, [character])[0]

    results = []
    for i in range(len(value)):
        for confusable in _read_or(_CONFUSABLES, value[i], []):
            results.append(value[:i] + confusable + value[i + 1:])
    results.append("".join(_first_confusable(ch) for ch in value))
    return list(filter(lambda neighbor: neighbor != value, results))


def control_characters(value):
    """The control-character neighbor class (section 3.5): for each injection character,
    three neighbors — prepended, appended, and inserted at the midpoint."""
    results = []
    for character in _INJECTION:
        results.append(character + value)
        results.append(value + character)
        mid = len(value) // 2
        results.append(value[:mid] + character + value[mid:])
    return results


def length_extensions(value):
    """The length-extension neighbor class (section 3.5): the value repeated 10, 100 and
    1000 times, and padded with 'A' toward the uint16 boundary and one megabyte."""
    return [
        value * 10,
        value * 100,
        value * 1000,
        value + ("A" * 65535),
        value + ("A" * 65536),
        value + ("A" * 1048575),
    ]


def encoding_variants(value):
    """The encoding-variant neighbor class (section 3.5): a UTF-16 byte-order-mark prefix,
    an overlong UTF-8 encoding, a double percent-encoding, a mixed-encoding prefix, and the
    whitespace-normalization attacks replacing a space with a non-breaking space or a line
    separator."""
    return [
        "﻿" + value,
        value.replace(" ", "\xa0"),
        value.replace(" ", " "),
        "".join("%25" + format(ord(ch), "02x") for ch in value),
        "".join("%c0%" + format(ord(ch), "02x") for ch in value),
        "À\u0080" + value,
    ]


def adversarial_neighbors(value):
    """The deduplicated union of the five neighbor classes with the original value removed
    (section 3.5): every neighbor must produce a rejection; one accepted reveals a
    vocabulary overlap, a case-sensitivity bug, a normalization flaw or an encoding hole."""
    union = (
        edit_distance_1(value)
        + unicode_confusables(value)
        + control_characters(value)
        + length_extensions(value)
        + encoding_variants(value)
    )
    deduped = list(dict.fromkeys(union))
    return list(filter(lambda neighbor: neighbor != value, deduped))


def generate_scaffolding(chain_name, links):
    """Generate the Gherkin step-module source for a chain from its link declarations
    (section 8.2): pure handlers wired through a register(registry) that returns the
    registry, matching honest-gherkin's step-module contract. The developer writes only
    the .feature files against it and never edits the generated file."""
    def _handler(link_name):
        return (
            f"def _step_{link_name}(context, **captures):\n"
            f"    # pure handler for the '{link_name}' link: takes the immutable context and bound\n"
            f"    # captures and returns a new context, never mutating a shared one.\n"
            f"    return context\n\n"
        )

    def _register(links):
        bindings = "".join(
            f'    registry = registry.bind("{chain_name}:{link["name"]}", _step_{link["name"]})\n'
            for link in links
        )
        return "def register(registry):\n" + bindings + "    return registry\n"

    header = (
        "# auto-generated scaffolding for honest-test — do not edit\n"
        f"# chain: {chain_name}\n"
        "# The developer writes the .feature file against the steps below; this file is regenerated.\n\n"
    )
    handlers = "".join(_handler(link["name"]) for link in links)
    return header + handlers + _register(links)
