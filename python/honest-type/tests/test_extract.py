"""Tests for HTTP + CLI extraction."""
from honest_type import extract_cli_tokens, extract_http_tokens


def test_extract_http_form():
    req = {"form": {"email": "a@b.co", "age": "30"}}
    tokens = extract_http_tokens(req)
    assert ("email", "a@b.co") in tokens
    assert ("age", "30") in tokens


def test_extract_http_mixes_sources():
    req = {
        "path_params": {"id": "42"},
        "query":       {"q": "hi"},
        "json":        {"tag": "x"},
    }
    tokens = extract_http_tokens(req)
    assert len(tokens) == 3


def test_extract_cli_eq():
    assert extract_cli_tokens(["--name=alice"]) == [("name", "alice")]


def test_extract_cli_pair():
    assert extract_cli_tokens(["--age", "30"]) == [("age", "30")]


def test_extract_cli_flag():
    assert extract_cli_tokens(["--verbose"]) == [("verbose", "true")]


def test_extract_cli_positional():
    assert extract_cli_tokens(["alice"]) == [("arg0", "alice")]


def test_extract_cli_mixed():
    out = extract_cli_tokens(["honest-tool", "--name=alice", "--age", "30", "extra"])
    assert out == [
        ("arg0", "honest-tool"),
        ("name", "alice"),
        ("age", "30"),
        ("arg1", "extra"),
    ]
