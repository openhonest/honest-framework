"""Tests for chain composition and fault-at-boundary."""
from honest_type import chain, compose_chain, pipe, run_chain, vocabulary
from honest_type.chain import link


def _add_one(x): return x + 1
def _double(x): return x * 2
def _explode(x): raise RuntimeError("boom")


def _vocab():
    return vocabulary({})


def test_pipe_composes_left_to_right():
    f = pipe(_add_one, _double)
    assert f(3) == 8  # (3+1)*2


def test_compose_chain_from_links():
    a = link("a", "pure", _add_one, _vocab())
    b = link("b", "pure", _double,  _vocab())
    c = chain("compute", [a, b])
    assert compose_chain(c)(3) == 8


def test_run_chain_returns_value():
    a = link("a", "pure", _add_one, _vocab())
    assert run_chain(chain("x", [a]), 5) == 6


def test_run_chain_catches_exception_as_fault():
    a = link("a", "pure", _explode, _vocab())
    result = run_chain(chain("bad", [a]), 1)
    assert result["code"] == "RuntimeError"
    assert result["category"] == "server"
    assert "boom" in result["message"]
