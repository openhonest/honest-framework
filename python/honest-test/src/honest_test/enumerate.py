"""Enumerate the Cartesian product of a collection of bounded sets.

A vocabulary is a dict {set_name: iterable_of_members}. The enumeration
yields every combination as a dict {set_name: member}.
"""
from __future__ import annotations

import itertools
from typing import Iterator


def enumerate_set_members(
    vocab: dict[str, list[str]],
) -> Iterator[dict[str, str]]:
    """Yield every Cartesian-product point of the vocabulary.

    Empty vocab yields one empty assignment.
    """
    if not vocab:
        yield {}
        return
    names = list(vocab.keys())
    values_lists = [vocab[n] for n in names]
    for combo in itertools.product(*values_lists):
        yield dict(zip(names, combo))
