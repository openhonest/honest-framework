"""Test-input generation (honest-test spec §3).

The vocabulary declaration is the test specification: honest-test reads it and
generates every valid input plus adversarial near-misses. These are pure
generators — no I/O, no honest-type import — operating on the recognizer shapes
honest-type and honest-check already produce.

Strategies (spec §2 classification -> §3 generation):
  - Set            -> enumerate every member; cartesian product across Sets
  - Numeric        -> Fibonacci sequence both directions from zero
  - Length-bounded -> every valid length 1..max, plus one over (must reject)
  - any value      -> five adversarial neighbor classes (spec §3.6)
"""
from __future__ import annotations

import itertools
from urllib.parse import quote

_ALPHA = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


# --- Set enumeration (spec §3.2) ------------------------------------------


def set_members(vocabulary: dict) -> dict:
    """Map each Set/insensitive base type to its member list.

    Recognizers are honest-type's runtime dict shape:
    {"kind": "set"|"insensitive", "members": frozenset} / {"kind": "predicate", "fn": ...}.
    """
    out: dict = {}
    for name, recognizer in vocabulary.get("base_types", {}).items():
        if recognizer.get("kind") in ("set", "insensitive"):
            members = recognizer.get("members")
            if members:
                out[name] = sorted(members)
    return out


def enumerate_sets(vocabulary: dict):
    """Yield every cartesian-product point across a vocabulary's Set types."""
    sets = set_members(vocabulary)
    if not sets:
        yield {}
        return
    names = list(sets)
    for combo in itertools.product(*(sets[n] for n in names)):
        yield dict(zip(names, combo))


# --- Numeric (spec §3.3) --------------------------------------------------


def fibonacci_sequence(limit: int = 1_000_000) -> list[int]:
    """Fibonacci values in both directions from zero, up to `limit`."""
    seq = [0, 1]
    while seq[-1] < limit:
        seq.append(seq[-2] + seq[-1])
    negative = [-x for x in seq if x > 0]
    return list(reversed(negative)) + seq


def numeric_values(limit: int = 1_000_000, as_float: bool = False):
    seq = fibonacci_sequence(limit)
    return [x / 100 for x in seq] if as_float else seq


# --- Length-bounded (spec §3.4) -------------------------------------------


def enumerate_lengths(max_len: int):
    """(valid, invalid): strings at every length 1..max_len, plus one over."""
    valid = [_ALPHA[:n] if n <= len(_ALPHA) else _ALPHA * (n // len(_ALPHA)) + _ALPHA[: n % len(_ALPHA)]
             for n in range(1, max_len + 1)]
    over = max_len + 1
    invalid = [_ALPHA[:over] if over <= len(_ALPHA)
               else _ALPHA * (over // len(_ALPHA)) + _ALPHA[: over % len(_ALPHA)]]
    return valid, invalid


# --- Adversarial neighbors (spec §3.6) ------------------------------------


def edit_distance_1(value: str) -> list[str]:
    chars = list(value)
    results: list[str] = []
    for i in range(len(chars)):                       # deletions
        results.append("".join(chars[:i] + chars[i + 1:]))
    for i in range(len(chars) + 1):                   # insertions
        for c in _ALPHA:
            results.append("".join(chars[:i] + [c] + chars[i:]))
    for i in range(len(chars)):                       # substitutions
        for c in _ALPHA:
            if c != chars[i]:
                results.append("".join(chars[:i] + [c] + chars[i + 1:]))
    results += [value.lower(), value.upper(), value.title()]   # case
    results += [" " + value, value + " "]                      # whitespace
    if len(value) >= 2:
        results.append(value[0] + " " + value[1:])
    return results


# Curated Unicode-confusables subset (TS #39); full set lives in the hub repo.
_CONFUSABLES = {
    "a": ["а", "ɑ", "ａ"],   # Cyrillic a, IPA alpha, fullwidth a
    "e": ["е", "ē", "ｅ"],   # Cyrillic e, e-macron, fullwidth e
    "o": ["о", "0", "ο", "ｏ"],
    "i": ["і", "1", "l"],
    "c": ["с", "ｃ"],
    "p": ["р", "ｐ"],
    "s": ["ѕ", "ｓ"],
    "x": ["х", "ｘ"],
}


def unicode_confusables(value: str) -> list[str]:
    results: list[str] = []
    for i, c in enumerate(value):
        for replacement in _CONFUSABLES.get(c, []):
            results.append(value[:i] + replacement + value[i + 1:])
    full = "".join(_CONFUSABLES[c][0] if c in _CONFUSABLES else c for c in value)
    if full != value:
        results.append(full)
    return results


_CONTROL_CHARS = [
    "\x00", "\x08", "\x09", "\x0a", "\x0d", "\x1b", "\x7f",
    "​", "‎", "‏", "‪", "‫", "‬",
    "‭", "‮", "﻿",
]


def control_characters(value: str) -> list[str]:
    results: list[str] = []
    mid = len(value) // 2
    for c in _CONTROL_CHARS:
        results += [c + value, value + c, value[:mid] + c + value[mid:]]
    return results


def length_extensions(value: str) -> list[str]:
    return [
        value * 10, value * 100, value * 1000,
        value + ("A" * 65535), value + ("A" * 65536),
        value + ("A" * 1048575),
    ]


def encoding_variants(value: str) -> list[str]:
    return [
        "﻿" + value,                       # BOM prefix
        quote(quote(value)),                    # double percent-encode
        value.replace(" ", "\xa0"),             # non-breaking space
        value.replace(" ", " "),           # line separator
    ]


def adversarial_neighbors(value: str) -> list[str]:
    """Deduplicated near-misses across all five classes, excluding the value."""
    seen: dict = {}   # ordered dedup
    for neighbor in (edit_distance_1(value) + unicode_confusables(value)
                     + control_characters(value) + length_extensions(value)
                     + encoding_variants(value)):
        if neighbor != value:
            seen[neighbor] = None
    return list(seen)
