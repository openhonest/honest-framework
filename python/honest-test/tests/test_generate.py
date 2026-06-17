"""honest-test §3 generation engine."""
from honest_test.generate import (
    adversarial_neighbors,
    edit_distance_1,
    encoding_variants,
    enumerate_lengths,
    enumerate_sets,
    fibonacci_sequence,
    length_extensions,
    unicode_confusables,
)


def test_fibonacci_both_directions():
    seq = fibonacci_sequence(20)
    assert 0 in seq and 1 in seq and 13 in seq
    assert -13 in seq and -1 in seq
    assert seq.index(-1) < seq.index(0)   # negatives precede positives


def test_enumerate_sets_cartesian():
    vocab = {"base_types": {
        "fmt": ("set", frozenset({"a", "b"})),
        "code": ("set", frozenset({"X"})),
        "num": ("predicate", None),         # predicates excluded from set enum
    }}
    points = list(enumerate_sets(vocab))
    assert {"fmt": "a", "code": "X"} in points
    assert {"fmt": "b", "code": "X"} in points
    assert len(points) == 2


def test_enumerate_lengths():
    valid, invalid = enumerate_lengths(3)
    assert [len(v) for v in valid] == [1, 2, 3]
    assert len(invalid[0]) == 4


def test_edit_distance_1():
    n = edit_distance_1("ab")
    assert "a" in n and "b" in n          # deletions
    assert "AB" in n                       # case
    assert " ab" in n and "ab " in n       # whitespace
    assert any(len(x) == 3 for x in n)     # insertions


def test_unicode_confusables():
    n = unicode_confusables("aeo")
    assert all(x != "aeo" for x in n)
    assert any("а" in x for x in n)        # Cyrillic a substituted


def test_control_characters_and_length_extensions():
    assert len(length_extensions("x")) == 6
    assert any("\x00" in x for x in adversarial_neighbors("USD"))


def test_encoding_variants():
    v = encoding_variants("a b")
    assert any("﻿" in x for x in v)            # BOM
    assert any("\xa0" in x for x in v)              # nbsp swap


def test_adversarial_neighbors_dedup_excludes_value():
    n = adversarial_neighbors("USD")
    assert "USD" not in n
    assert len(n) == len(set(n))                    # deduplicated
    assert len(n) > 50                              # rich neighbor set
