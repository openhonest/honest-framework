"""Adversarial input generation (section 3.5).

For every Set member, honest-test generates adversarial neighbours across several classes.
Every neighbour must produce a rejection; a neighbour that is accepted reveals a vocabulary
overlap, a case-sensitivity bug, a normalisation flaw, or an encoding vulnerability.

These are pure string generators. Classes 1-4 (edit-distance-1, Unicode confusables, control
characters, length extensions) and the string-valued members of Class 5 (encoding variants)
are implemented here. The two byte-level Class 5 variants (overlong UTF-8, mixed encoding)
need a bytes channel and a representation decision; they are deferred and not yet unioned.
The full reference vocabularies live in the hub conformance fixtures. Every non-ASCII or
non-printable character is written as a backslash-u escape, so the source is pure ASCII with
no hidden look-alikes.
"""

from urllib.parse import quote

_ALPHA = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

# Curated Unicode-confusables subset (Technical Standard #39). The full list lives in the
# hub conformance fixture; this is the spec's worked subset.
_CONFUSABLES = {
    "a": ["\u0430", "\u0251", "\uff41", "\U0001d41a"],  # Cyrillic a, IPA alpha, fullwidth a, math a
    "e": ["\u0435", "\u0113", "\uff45"],                # Cyrillic e, e-macron, fullwidth e
    "o": ["\u043e", "0", "\u03bf", "\uff4f"],           # Cyrillic o, digit zero, Greek omicron, fullwidth o
    "i": ["\u0456", "\u04cf", "1", "l"],                # Cyrillic i, palochka, digit one, latin L
}

# C0/C1 control codes, bidi overrides, and zero-width characters (section 3.5, Class 3).
_CONTROL_INJECTIONS = (
    "\x00", "\x08", "\x09", "\x0a", "\x0d", "\x1b", "\x7f",
    "\u200b", "\u200e", "\u200f", "\u202a", "\u202b", "\u202c",
    "\u202d", "\u202e", "\ufeff",
)


def edit_distance_1(value):
    """Class 1: deletions, insertions, substitutions, case variations, whitespace variations."""
    chars = list(value)
    results = []
    for i in range(len(chars)):
        results.append("".join(chars[:i] + chars[i + 1:]))
    for i in range(len(chars) + 1):
        for char in _ALPHA:
            results.append("".join(chars[:i] + [char] + chars[i:]))
    for i in range(len(chars)):
        for char in _ALPHA:
            if char != chars[i]:
                results.append("".join(chars[:i] + [char] + chars[i + 1:]))
    results.extend([value.lower(), value.upper(), value.title(), " " + value, value + " "])
    if len(value) >= 2:
        results.append(value[0] + " " + value[1:])
    return results


def unicode_confusables(value):
    """Class 2: visually-similar characters from other Unicode blocks, one position at a time,
    plus a full homoglyph replacement."""
    results = []
    for i in range(len(value)):
        for replacement in _CONFUSABLES.get(value[i], []):
            results.append(value[:i] + replacement + value[i + 1:])
    full = "".join(_CONFUSABLES.get(char, [char])[0] for char in value)
    if full != value:
        results.append(full)
    return results


def control_characters(value):
    """Class 3: C0/C1 controls, bidi overrides, zero-width characters: prepended, appended,
    and inserted at the midpoint."""
    mid = len(value) // 2
    results = []
    for char in _CONTROL_INJECTIONS:
        results.extend([char + value, value + char, value[:mid] + char + value[mid:]])
    return results


def length_extensions(value):
    """Class 4: inputs padded to sizes that expose fixed-buffer and truncation assumptions."""
    return [
        value * 10,
        value * 100,
        value * 1000,
        value + ("A" * 65535),
        value + ("A" * 65536),
        value + ("A" * 1048575),
    ]


def encoding_variants(value):
    """Class 5 (string-valued subset): BOM prefix, double percent-encoding, and whitespace
    normalisation attacks. Byte-level variants (overlong UTF-8, mixed encoding) are deferred."""
    return [
        "\ufeff" + value,
        quote(quote(value)),
        value.replace(" ", "\xa0"),
        value.replace(" ", "\u2028"),
    ]


_CLASSES = (
    edit_distance_1,
    unicode_confusables,
    control_characters,
    length_extensions,
    encoding_variants,
)


def adversarial_neighbours(value):
    """Every adversarial neighbour of a value, de-duplicated and excluding the value itself
    (section 3.5). Each must be rejected by a correct recognizer."""
    seen = set()
    for generate in _CLASSES:
        seen.update(generate(value))
    seen.discard(value)
    return sorted(seen)


# US spelling alias: the spec uses "neighbors".
adversarial_neighbors = adversarial_neighbours
