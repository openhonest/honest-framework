"""Tests for each rule check."""
from honest_check import check_source


def _has_rule(report, rule_id):
    return any(d["rule_id"] == rule_id for d in report["diagnostics"])


# --- HC-P003: no classes ---------------------------------------------------


def test_p003_flags_plain_class():
    report = check_source("class Foo:\n    pass\n")
    assert _has_rule(report, "HC-P003")
    assert report["total_errors"] >= 1


def test_p003_allows_typed_dict_subclass():
    src = (
        "from typing import TypedDict\n"
        "class User(TypedDict):\n"
        "    email: str\n"
    )
    report = check_source(src)
    assert not _has_rule(report, "HC-P003")


def test_p003_allows_protocol():
    src = (
        "from typing import Protocol\n"
        "class Ser(Protocol):\n"
        "    def ser(self) -> str: ...\n"
    )
    report = check_source(src)
    assert not _has_rule(report, "HC-P003")


def test_p003_allows_exception_subclass():
    src = "class BadThing(Exception): pass\n"
    report = check_source(src)
    assert not _has_rule(report, "HC-P003")


def test_p003_flags_bare_class_regardless_of_name():
    # Spec §4.1/§5.3: a bare class (no declared base) is a violation, with no
    # name-suffix exception. The prior "Error-suffix is allowed" behavior was
    # drift; an exception type must explicitly subclass Exception.
    src = "class FooError: pass\n"
    report = check_source(src)
    assert _has_rule(report, "HC-P003")



# --- HC-P001: if/elif dispatch --------------------------------------------


def test_p001_flags_three_way_dispatch():
    src = (
        "def handle(kind):\n"
        "    if kind == 'a':\n"
        "        return 1\n"
        "    elif kind == 'b':\n"
        "        return 2\n"
        "    elif kind == 'c':\n"
        "        return 3\n"
    )
    report = check_source(src)
    assert _has_rule(report, "HC-P001")


def test_p001_does_not_flag_single_if():
    src = (
        "def handle(x):\n"
        "    if x == 1:\n"
        "        return 0\n"
        "    return 1\n"
    )
    report = check_source(src)
    assert not _has_rule(report, "HC-P001")


def test_p001_does_not_flag_two_branch():
    src = (
        "def handle(x):\n"
        "    if x == 1:\n"
        "        return 'a'\n"
        "    elif x == 2:\n"
        "        return 'b'\n"
    )
    # Two branches are just a binary decision, not a discriminant dispatch
    # over an open set. Threshold is 3+ branches.
    report = check_source(src)
    assert not _has_rule(report, "HC-P001")


# --- HC011: catch-all recognizer (spec §8; was mislabeled HC-P014) --------


def test_hc011_flags_always_true_lambda():
    src = "r = lambda s: True\n"
    report = check_source(src)
    assert _has_rule(report, "HC011")


def test_hc011_flags_always_true_function():
    src = "def recognize(s): return True\n"
    report = check_source(src)
    assert _has_rule(report, "HC011")


def test_hc011_does_not_flag_real_recognizer():
    src = "r = lambda s: '@' in s\n"
    report = check_source(src)
    assert not _has_rule(report, "HC011")


# --- HC003 / HC006 / HC007: construction-time rules via the decl graph ----


def test_hc003_flags_overlapping_sets():
    src = (
        "from honest_type import vocabulary\n"
        "v = vocabulary({'a': {'X', 'Y'}, 'b': {'Y', 'Z'}})\n"
    )
    report = check_source(src)
    assert any(d["rule_id"] == "HC003" and d["severity"] == "error"
               for d in report["diagnostics"])


def test_hc003_clean_for_disjoint_sets():
    src = (
        "from honest_type import vocabulary\n"
        "v = vocabulary({'a': {'X'}, 'b': {'Y'}})\n"
    )
    report = check_source(src)
    assert not any(d["rule_id"] == "HC003" and d["severity"] == "error"
                   for d in report["diagnostics"])


def test_hc006_flags_composed_unknown_base():
    src = (
        "from honest_type import vocabulary, composed\n"
        "v = vocabulary({'fmt': {'currency'}},\n"
        "  composed_types=[composed('cp', requires={'missing': 'currency'}, captures='fmt')])\n"
    )
    report = check_source(src)
    assert _has_rule(report, "HC006")


def test_hc006_clean_when_bases_known():
    src = (
        "from honest_type import vocabulary, composed\n"
        "v = vocabulary({'fmt': {'currency'}, 'n': {'1'}},\n"
        "  composed_types=[composed('cp', requires={'fmt': 'currency'}, captures='n')])\n"
    )
    report = check_source(src)
    assert not _has_rule(report, "HC006")


def test_hc007_flags_empty_chain():
    src = "from honest_type import chain\nc = chain()\n"
    report = check_source(src)
    assert _has_rule(report, "HC007")


def test_hc007_clean_for_nonempty_chain():
    src = "from honest_type import chain\nc = chain(a, b)\n"
    report = check_source(src)
    assert not _has_rule(report, "HC007")


# --- Aggregation -----------------------------------------------------------


def test_multiple_violations_aggregated():
    src = (
        "class Foo: pass\n"
        "class Bar: pass\n"
        "def dispatch(x):\n"
        "    if x == 1: return 1\n"
        "    elif x == 2: return 2\n"
        "    elif x == 3: return 3\n"
    )
    report = check_source(src)
    assert report["total_errors"] >= 3


def test_syntax_error_becomes_diagnostic():
    report = check_source("def bad(:\n    pass\n")
    assert report["total_errors"] >= 1
    assert report["diagnostics"][0]["rule_id"] == "HC-SYN"
