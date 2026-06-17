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
    "  transitions={('pending', 'pay'): 'paid'%s}, initial=%s, terminal=['paid'])\n"
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


# --- Unit 3b: I/O detection + suppression ---------------------------------


def _errors_for(report, rule_id):
    return [d for d in report["diagnostics"]
            if d["rule_id"] == rule_id and d["severity"] == "error"]


def test_hc_p004_flags_io_in_plain_function():
    src = "def load():\n    return open('x')\n"
    report = check_source(src)
    assert _errors_for(report, "HC-P004")


def test_hc_p004_flags_nondeterministic():
    src = "import time\ndef stamp():\n    return time.time()\n"
    report = check_source(src)
    assert _errors_for(report, "HC-P004")


def test_hc_p004_clean_for_boundary_decorated():
    src = (
        "from honest_type import link\n"
        "@link(boundary=True)\n"
        "def load(m):\n"
        "    return open('x')\n"
    )
    report = check_source(src)
    assert not _errors_for(report, "HC-P004")


def test_hc_p004_clean_when_suppressed_file_level():
    src = "# honest: disable HC-P004\ndef load():\n    return open('x')\n"
    report = check_source(src)
    assert not _errors_for(report, "HC-P004")


def test_hc_p005_flags_isinstance_in_business_logic():
    src = "def classify(x):\n    return isinstance(x, str)\n"
    report = check_source(src)
    assert _has_rule(report, "HC-P005")


def test_suppression_inline_ignore():
    src = "class Foo:  # honest: ignore HC-P003\n    pass\n"
    report = check_source(src)
    assert not _errors_for(report, "HC-P003")


def test_suppression_records_info():
    src = "class Foo:  # honest: ignore HC-P003\n    pass\n"
    report = check_source(src)
    assert any(d["rule_id"] == "HC-P003" and d["severity"] == "info"
               for d in report["diagnostics"])


# --- Unit 3c: static state-machine rules ----------------------------------


def test_hc_sm04_flags_dead_state():
    # 'paid' has no outgoing transition and is not terminal.
    src = (
        "from honest_state import state_machine\n"
        "m = state_machine(states={'pending', 'paid'}, events={'pay'},\n"
        "  transitions={('pending', 'pay'): 'paid'}, initial='pending')\n"
    )
    report = check_source(src)
    assert _has_rule(report, "HC-SM04")


def test_hc_sm04_clean_when_terminal_declared():
    src = (
        "from honest_state import state_machine\n"
        "m = state_machine(states={'pending', 'paid'}, events={'pay'},\n"
        "  transitions={('pending', 'pay'): 'paid'}, initial='pending',\n"
        "  terminal=['paid'])\n"
    )
    report = check_source(src)
    assert not _has_rule(report, "HC-SM04")


def test_hc_sm03_flags_unreachable_state():
    # 'orphan' is in states but no transition reaches it.
    src = (
        "from honest_state import state_machine\n"
        "m = state_machine(states={'a', 'b', 'orphan'}, events={'go'},\n"
        "  transitions={('a', 'go'): 'b', ('b', 'go'): 'a'}, initial='a',\n"
        "  terminal=['orphan'])\n"
    )
    report = check_source(src)
    assert _has_rule(report, "HC-SM03")


def test_hc_sm06_flags_undeclared_field_write():
    src = (
        "from honest_state import state_machine\n"
        "m = state_machine(states={'open', 'done'}, events={'finish'},\n"
        "  state_fields=['status'],\n"
        "  transitions={('open', 'finish'): lambda s, e: {**s, 'status': 'done', 'created_at': None}},\n"
        "  initial='open', terminal=['done'])\n"
    )
    report = check_source(src)
    assert any(d["rule_id"] == "HC-SM06" and d["severity"] == "error"
               for d in report["diagnostics"])


def test_hc_sm06_clean_when_fields_declared():
    src = (
        "from honest_state import state_machine\n"
        "m = state_machine(states={'open', 'done'}, events={'finish'},\n"
        "  state_fields=['status'],\n"
        "  transitions={('open', 'finish'): lambda s, e: {**s, 'status': 'done'}},\n"
        "  initial='open', terminal=['done'])\n"
    )
    report = check_source(src)
    assert not _has_rule(report, "HC-SM06")


# --- Unit 3d: vocabulary/binding static rules -----------------------------


def test_hc004_flags_dead_vocabulary_type():
    src = (
        "from honest_type import vocabulary, binding, classify\n"
        "v = vocabulary({'a': {'X'}, 'dead': {'Y'}})\n"
        "b = binding({'a': 'slot_a'})\n"
        "classify(['X'], v, b)\n"
    )
    report = check_source(src)
    assert _has_rule(report, "HC004")


def test_hc005_flags_unused_binding_entry():
    src = (
        "from honest_type import vocabulary, binding, classify\n"
        "v = vocabulary({'a': {'X'}})\n"
        "b = binding({'a': 'slot_a', 'ghost': 'slot_g'})\n"
        "classify(['X'], v, b)\n"
    )
    report = check_source(src)
    assert _has_rule(report, "HC005")


def test_hc004_hc005_clean_when_consistent():
    src = (
        "from honest_type import vocabulary, binding, classify\n"
        "v = vocabulary({'a': {'X'}})\n"
        "b = binding({'a': 'slot_a'})\n"
        "classify(['X'], v, b)\n"
    )
    report = check_source(src)
    assert not _has_rule(report, "HC004")
    assert not _has_rule(report, "HC005")


def test_hc_p014_flags_shared_recognizer_reference():
    # sender and receiver are backed by the same recognizer reference (user_id);
    # both bound to slots -> swap-vulnerable.
    src = (
        "from honest_type import vocabulary, binding, classify, predicate\n"
        "user_id = predicate(lambda s: len(s) == 4)\n"
        "v = vocabulary({'sender': user_id, 'receiver': user_id})\n"
        "b = binding({'sender': 'from_slot', 'receiver': 'to_slot'})\n"
        "classify(['abcd'], v, b)\n"
    )
    report = check_source(src)
    assert any(d["rule_id"] == "HC-P014" and d["severity"] == "error"
               for d in report["diagnostics"])


def test_hc_p014_clean_for_distinct_recognizers():
    src = (
        "from honest_type import vocabulary, binding, classify, predicate\n"
        "snd = predicate(lambda s: s.startswith('snd_'))\n"
        "rcv = predicate(lambda s: s.startswith('rcv_'))\n"
        "v = vocabulary({'sender': snd, 'receiver': rcv})\n"
        "b = binding({'sender': 'from_slot', 'receiver': 'to_slot'})\n"
        "classify(['snd_1'], v, b)\n"
    )
    report = check_source(src)
    assert not _has_rule(report, "HC-P014")
