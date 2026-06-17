"""Tests for vocabulary construction + merging."""
import pytest

from honest_type import merge_vocabularies, vocabulary


def test_vocabulary_wraps_dict():
    r = lambda s: True  # noqa: E731
    v = vocabulary({"any": r})
    assert v["recognizers"]["any"] is r


def test_merge_disjoint():
    r1 = lambda s: True  # noqa: E731
    r2 = lambda s: False  # noqa: E731
    merged = merge_vocabularies(vocabulary({"a": r1}), vocabulary({"b": r2}))
    assert set(merged["recognizers"]) == {"a", "b"}


def test_merge_same_recognizer_ok():
    r = lambda s: True  # noqa: E731
    merged = merge_vocabularies(vocabulary({"x": r}), vocabulary({"x": r}))
    assert merged["recognizers"]["x"] is r


def test_merge_collision_raises():
    r1 = lambda s: True  # noqa: E731
    r2 = lambda s: False  # noqa: E731
    with pytest.raises(ValueError, match="collision"):
        merge_vocabularies(vocabulary({"x": r1}), vocabulary({"x": r2}))
