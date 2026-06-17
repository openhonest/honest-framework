"""Vocabulary constructors + composition.

A vocabulary is just a dict of named recognizers. Adding one is appending
to the dict. Merging two is union — but we fail loudly on type-name
collisions so two vocabularies don't silently disagree on what "email"
means.
"""
from __future__ import annotations

from honest_type.types import Recognizer, Vocabulary


def vocabulary(recognizers: dict[str, Recognizer]) -> Vocabulary:
    """Pure constructor. Input is a plain dict; output is a Vocabulary."""
    return Vocabulary(recognizers=dict(recognizers))


def merge_vocabularies(*vocabs: Vocabulary) -> Vocabulary:
    """Union of recognizer dicts. Raises ValueError on a type-name collision
    where two vocabularies declare the same name but with different
    predicates (object identity).
    """
    merged: dict[str, Recognizer] = {}
    for v in vocabs:
        for name, recognizer in v["recognizers"].items():
            existing = merged.get(name)
            if existing is not None and existing is not recognizer:
                raise ValueError(
                    f"vocabulary merge collision on type {name!r}: "
                    f"two different recognizers declared"
                )
            merged[name] = recognizer
    return Vocabulary(recognizers=merged)
