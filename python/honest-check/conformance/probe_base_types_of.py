"""Honest probe for honest-check's base_types_of (Scenario: base_types_of).

base_types_of returns dict<str, BaseType> (the .hd types): each name mapped to a
BaseType record {kind, members, recognizer}. kind 'set' carries members (the string
set) with recognizer NOTHING; kind 'predicate' carries the recognizer's value node
(opaque, honest-check cannot run it, HC009) with members NOTHING. The case parses a
real dict literal with honest-parse and hands the real `dictionary` node in.

The 'set' entry's members are pinned to the literal string set. A predicate's
recognizer is a parse node whose identity cannot be a literal, so that entry is
pinned by its kind and the node's source text.
"""

from honest_parse import parse, walk


def _dictionary_node(source):
    root = parse(source.encode("utf-8"), "python").root_node
    for node in walk(root):
        if node.type == "dictionary":
            return node
    return None


_SOURCE = 'vocab = {"color": {"red", "green"}, "check": lambda s: s}\n'


def probe_base_types_of():
    """base_types_of maps a set member type to a frozenset and a predicate type to its node."""
    try:
        from honest_check import base_types_of
    except ImportError as exc:
        return [f"cannot import base_types_of: {exc}"]

    ctx = {
        "root": None,
        "nodes": [],
        "aliases": {},
        "roles": {},
        "source": _SOURCE.encode("utf-8"),
        "path": "case.py",
        "rule_config": {},
    }
    dictionary_node = _dictionary_node(_SOURCE)
    if dictionary_node is None:
        return [f"test setup: no dictionary node in {_SOURCE!r}"]

    got = base_types_of(ctx, dictionary_node)
    bad = []

    if not isinstance(got, dict):
        return [f"base_types_of(...) -> {got!r}, expected a dict of name -> BaseType record"]

    # The 'set' entry: a BaseType record {kind 'set', members the string set, recognizer NOTHING}.
    color = got.get("color")
    if not (isinstance(color, dict) and color.get("kind") == "set"
            and set(color.get("members") or ()) == {"red", "green"} and color.get("recognizer") is None):
        bad.append(
            f"base_types_of['color'] -> {color!r}, expected "
            f"{{'kind': 'set', 'members': {{'red', 'green'}}, 'recognizer': None}}"
        )

    # The 'predicate' entry: {kind 'predicate', members NOTHING, recognizer the value node}.
    check = got.get("check")
    if not (isinstance(check, dict) and check.get("kind") == "predicate" and check.get("members") is None):
        bad.append(f"base_types_of['check'] -> {check!r}, expected a 'predicate' BaseType record")
    elif getattr(check.get("recognizer"), "text", b"").decode("utf-8") != "lambda s: s":
        payload_text = getattr(check.get("recognizer"), "text", b"").decode("utf-8")
        bad.append(
            f"base_types_of['check'] recognizer node text -> {payload_text!r}, expected 'lambda s: s'"
        )
    return bad
