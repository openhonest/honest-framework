"""Tests for the normative §4.2 watch-list matcher."""
from honest_check.watchlists import (
    IO_PYTHON,
    NONDETERMINISTIC_PYTHON,
    matches_watchlist,
)


def test_exact_match():
    assert matches_watchlist("open", IO_PYTHON)
    assert matches_watchlist("print", IO_PYTHON)
    assert not matches_watchlist("len", IO_PYTHON)


def test_dotstar_prefix_match():
    # "requests.*" traps requests.get / requests.post
    assert matches_watchlist("requests.get", IO_PYTHON)
    assert matches_watchlist("socket.socket", IO_PYTHON)
    assert matches_watchlist("logging.info", IO_PYTHON)
    assert not matches_watchlist("requestsx", IO_PYTHON)


def test_trailing_star_prefix_match():
    # "os.spawn*" traps os.spawnv / os.spawnlp
    assert matches_watchlist("os.spawnv", IO_PYTHON)
    assert matches_watchlist("os.spawnlp", IO_PYTHON)


def test_nondeterministic_list():
    assert matches_watchlist("time.time", NONDETERMINISTIC_PYTHON)
    assert matches_watchlist("random.choice", NONDETERMINISTIC_PYTHON)
    assert matches_watchlist("os.getenv", NONDETERMINISTIC_PYTHON)
    assert matches_watchlist("id", NONDETERMINISTIC_PYTHON)
    assert not matches_watchlist("math.floor", NONDETERMINISTIC_PYTHON)
