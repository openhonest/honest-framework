"""Tests for classification."""
import re

from honest_type import classify_token, vocabulary


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
INT_RE = re.compile(r"^-?\d+$")


def _vocab():
    return vocabulary({
        "email": lambda s: bool(EMAIL_RE.match(s)),
        "int":   lambda s: bool(INT_RE.match(s)),
    })


def test_classify_email_returns_ticket():
    result = classify_token("alice@example.com", _vocab())
    assert result == {
        "type": "email", "value": "alice@example.com", "slot": ""
    }


def test_classify_int_returns_ticket():
    result = classify_token("42", _vocab())
    assert result["type"] == "int"


def test_classify_unrecognized_returns_rejection():
    result = classify_token("not-a-thing", _vocab())
    assert result["reason"] == "unrecognized_shape"
    assert set(result["attempted"]) == {"email", "int"}


def test_classify_overlap_returns_rejection():
    v = vocabulary({
        "any_a": lambda s: "a" in s,
        "any_b": lambda s: "b" in s,
    })
    result = classify_token("abc", v)
    assert "recognizer_overlap" in result["reason"]
    assert "any_a" in result["reason"]
    assert "any_b" in result["reason"]
