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


# --- HC-SM01 / HC-SM02 / HC-SM05: state-machine construction (Core) -------

_SM_BASE = (
    "from honest_state import state_machine\n"
    "m = state_machine(states={'pending', 'paid'}, events={'pay'},\n"
    "  transitions={('pending', 'pay'): 'paid'%s}, initial=%s)\n"
)


def test_hc_sm01_flags_unknown_state():
    src = _SM_BASE % (", ('unknown', 'pay'): 'paid'", "'pending'")
    report = check_source(src)
    assert _has_rule(report, "HC-SM01")


def test_hc_sm02_flags_unknown_event():
    src = _SM_BASE % (", ('pending', 'zap'): 'paid'", "'pending'")
    report = check_source(src)
    assert _has_rule(report, "HC-SM02")


def test_hc_sm05_flags_bad_initial():
    src = _SM_BASE % ("", "'nope'")
    report = check_source(src)
    assert _has_rule(report, "HC-SM05")


def test_sm_clean_valid_machine():
    src = _SM_BASE % ("", "'pending'")
    report = check_source(src)
    assert not any(d["rule_id"].startswith("HC-SM") for d in report["diagnostics"])


def test_sm_states_from_vocabulary_call():
    # states/events expressed as vocabulary(...) calls, per honest-type §7c.
    src = (
        "from honest_state import state_machine\n"
        "from honest_type import vocabulary\n"
        "m = state_machine(\n"
        "  states=vocabulary({'s': {'pending', 'paid'}}),\n"
        "  events=vocabulary({'e': {'pay'}}),\n"
        "  transitions={('ghost', 'pay'): 'paid'}, initial='pending')\n"
    )
    report = check_source(src)
    assert _has_rule(report, "HC-SM01")


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


# --- Unit 3a: AST-structural principle rules ------------------------------


def test_hc_p002_flags_mutating_method():
    src = (
        "class Counter:\n"
        "    def bump(self):\n"
        "        self.n = self.n + 1\n"
    )
    report = check_source(src)
    assert any(d["rule_id"] == "HC-P002" and d["severity"] == "error"
               for d in report["diagnostics"])


def test_hc_p002_init_mutation_is_warning():
    src = (
        "class Point:\n"
        "    def __init__(self, x):\n"
        "        self.x = x\n"
    )
    report = check_source(src)
    p002 = [d for d in report["diagnostics"] if d["rule_id"] == "HC-P002"]
    assert p002 and all(d["severity"] == "warning" for d in p002)


def test_hc_p007_flags_underscore_instance_state():
    src = (
        "class Service:\n"
        "    def __init__(self):\n"
        "        self._cache = {}\n"
    )
    report = check_source(src)
    assert _has_rule(report, "HC-P007")


def test_hc_p011_flags_lifecycle_hook():
    src = "def setup(el):\n    el.addEventListener('click', handler)\n"
    report = check_source(src)
    assert _has_rule(report, "HC-P011")


def test_hc_p016_flags_nonlocal_mutation():
    src = (
        "def outer():\n"
        "    total = 0\n"
        "    def inner(x):\n"
        "        nonlocal total\n"
        "        total = total + x\n"
        "    return inner\n"
    )
    report = check_source(src)
    assert _has_rule(report, "HC-P016")


def test_hc_p016_clean_without_mutation():
    src = (
        "def outer():\n"
        "    total = 0\n"
        "    def inner(x):\n"
        "        return total + x\n"
        "    return inner\n"
    )
    report = check_source(src)
    assert not _has_rule(report, "HC-P016")
