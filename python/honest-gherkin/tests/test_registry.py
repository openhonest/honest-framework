"""Tests for the step registry + pattern matching."""
import pytest

from honest_gherkin import empty_registry, match_step, register_step
from honest_gherkin.registry import (
    AmbiguousStepError,
    StepUnmatchedError,
    compile_pattern,
)


def _noop(context):
    return context


def test_empty_registry_has_no_patterns():
    r = empty_registry()
    assert r == {"patterns": []}


def test_register_returns_a_new_registry():
    r = empty_registry()
    r2 = register_step(r, "given", r"a vocab", _noop)
    assert r == {"patterns": []}
    assert len(r2["patterns"]) == 1


def test_match_step_returns_captures():
    r = register_step(empty_registry(), "given", r"the value {n:int}", _noop)
    step = {"kind": "given", "text": "the value 42", "source_line": 1}
    m = match_step(step, r)
    assert m["captures"] == {"n": 42}


def test_unmatched_step_raises():
    r = empty_registry()
    step = {"kind": "given", "text": "nothing matches", "source_line": 1}
    with pytest.raises(StepUnmatchedError):
        match_step(step, r)


def test_ambiguous_step_raises():
    r = empty_registry()
    r = register_step(r, "given", r"the value \d+", _noop)
    r = register_step(r, "given", r"the value {n}", _noop)
    step = {"kind": "given", "text": "the value 42", "source_line": 1}
    with pytest.raises(AmbiguousStepError):
        match_step(step, r)


def test_compile_pattern_str_placeholder():
    regex, coercions = compile_pattern(r"classify {tok}")
    assert coercions == {"tok": str}
    assert regex.match("classify alice") is not None


def test_compile_pattern_int_placeholder():
    regex, coercions = compile_pattern(r"the value {n:int}")
    assert coercions == {"n": int}
    assert regex.match("the value 42") is not None
    assert regex.match("the value abc") is None


def test_compile_pattern_float_placeholder():
    regex, coercions = compile_pattern(r"the score {s:float}")
    assert coercions == {"s": float}
    assert regex.match("the score 3.14") is not None
