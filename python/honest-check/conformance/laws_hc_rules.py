"""honest-check conformance: per-rule branch laws for rules.py + declgraph.py.

The two existing harnesses (run_conformance.py, laws_hc.py) drive the I/O shells and the
headline positive/negative example per rule. This file carries the *residual* rule branches
those two miss: every clean (no-violation) path, every sub-condition of a rule (a class with a
base vs without, an if-chain that dispatches vs one that does not, a try with an except vs a
try/finally, a vocabulary merge via `|`, a classify(...) positional pairing, an inline-vs-named
state-machine vocabulary, a maybe()-wrapped capture, an aliased import), and the declaration-graph
node shapes (binding / role / state-machine / reachability / auth / persist taint) that the JSON
suite never declares. Each case is data: a source snippet plus the rule ids that must fire and the
ids that must not, all fed through `check_source` and asserted by id. A snippet that targets a rule
verifies that rule actually fires; a clean snippet verifies it stays silent.

The conformance directory is outside the honest-check lint gate, so the snippets are free to
contain classes, I/O, if/elif chains, and so on — they are the violations being detected, not code
the framework ships.

Honest residue. A handful of lines in rules.py and declgraph.py are unreachable from
check_source and cannot be reached by any honest crafted input either, so they are NOT faked:

  Defensive field-None / args-None guards (the codebase's uniform `if x is None: continue`
  style) on tree-sitter fields that are always present in a parsed tree: a function_definition
  always has a body, an assignment a left, an attribute an object and attribute, a call a
  function and an argument_list, a keyword_argument a name and value, an aliased_import a name
  and alias, a for-statement a left. These guards live inside `walk` loops over already
  type-filtered, cleanly-parsed nodes. Tree-sitter only omits a required field on malformed
  input, and on malformed input it does NOT emit the target node type with the field absent: it
  emits an ERROR node (so the loop's `node.type == X` filter skips it) or synthesizes a missing
  child (so the field is non-None). Empirically verified per node type. Direct calls cannot reach
  them either: the guard sits AFTER the type filter, so a node that reaches it is a real parsed
  node of that type, which always has the field. (The args-None variants on the EXTRACTABLE pure
  accessors — keyword_args, positional_arg_count, _dictionary_arg, _parse_composed, function_calls
  — sit at function entry and ARE pinned by direct call with a non-call node in
  _probe_internal_helpers; only the in-loop variants are irreducible.)
  Irreducible: rules.py 253, 260, 313, 490->483, 517, 907, 1304, 1348; declgraph.py 44->48, 73,
  80, 147, 326, 348, 469, 544->548, 569->564.

  Value-never-None on a string node: string_value of a confirmed `string` node returns "" or the
  content, never None, so the `value is not None` False sides are dead. rules.py 911->913,
  1061->1058; declgraph.py 184->192 (captures = maybe(...) where the maybe-call's argument_list,
  always present, makes the inner-None side unreachable).

  Malformed-comparison guard: _equality_target's `len(operands) < 2` after confirming a `==`
  child — tree-sitter never yields a `==` comparison with fewer than two operands (a single-sided
  `x ==` parses to an ERROR node, not a comparison_operator). rules.py 140.

  Two latent `is`-identity bugs (real findings, now FIXED in src by the maintainer with `==`).
  The fixes made the previously dead exemption branches reachable, and the cases below now assert
  the corrected behavior:
    - rules.py _is_value_load (lines 503, 505): an identifier used as an attribute name (`o.NAME`)
      or a keyword-argument name (`g(NAME=1)`) is a name label, not a value load, so the function
      returns False and HC-P004 does not fire on it. Pinned by p004_attribute_and_keyword_occurrence
      and _probe_internal_helpers.
    - declgraph.py resolve_aliases (line 40 `continue`): the module-name child is now skipped by
      equality. Covered by alias_unrelated_imports_clean's `from honest_type import ... as ...`.
"""

from honest_check import check_source
from honest_check.rules import (
    _call_name,
    _check_global_reads,
    _class_methods,
    _direct_nonlocal_names,
    _is_value_load,
    _local_names,
    _orchestrator_call_sequence,
    _produced_slot_keys,
    _self_attr_writes,
)
from honest_check.declgraph import (
    function_calls,
    keyword_args,
    positional_arg_count,
    resolve_aliases,
    string_value,
    string_list,
    transition_table,
    vocabulary_members,
    _derivation_signature,
    _dictionary_arg,
    _parse_composed,
)
from honest_parse import parse_python, node_text, walk as _w


def _rules(source: str) -> list[str]:
    return [d["rule"] for d in check_source(source, "f.py")]


# Each case: (label, source, must_fire, must_not_fire).
# must_fire   — rule ids that MUST appear in the diagnostics for this snippet.
# must_not_fire — rule ids that MUST NOT appear (clean-path / negative assertions).
_CASES: list[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = []


def _case(label, source, must_fire=(), must_not_fire=()):
    _CASES.append((label, source, tuple(must_fire), tuple(must_not_fire)))


# ----------------------------------------------------------------- HC-P003 class shapes

_case(
    "p003_bare_class",
    "class Widget:\n    pass\n",
    must_fire=("HC-P003",),
)
_case(
    "p003_allowed_base_typeddict",
    "from typing import TypedDict\nclass Row(TypedDict):\n    a: int\n",
    must_not_fire=("HC-P003",),
)
_case(
    "p003_allowed_base_protocol_dotted_subscript",
    "import typing\nclass P(typing.Protocol[int]):\n    pass\n",
    must_not_fire=("HC-P003",),
)
_case(
    "p003_disallowed_base",
    "class Widget(Gadget):\n    pass\n",
    must_fire=("HC-P003",),
)
_case(
    "p003_total_keyword_only",
    "from typing import TypedDict\nclass Row(TypedDict, total=False):\n    a: int\n",
    must_not_fire=("HC-P003",),
)


# ----------------------------------------------------------------- HC-P010 non-serializable return

# Returning a class instance (a PascalCase constructor that is not an in-file TypedDict) is a
# non-serializable return — the framework returns dicts/TypedDicts, not objects.
_case(
    "p010_returns_class_instance",
    "def f():\n    return Widget(1)\n",
    must_fire=("HC-P010",),
)
_case(
    "p010_returns_typeddict_clean",
    "from typing import TypedDict\nclass Row(TypedDict):\n    a: int\ndef f():\n    return Row(a=1)\n",
    must_not_fire=("HC-P010",),
)
_case(
    "p010_returns_lowercase_call_clean",
    "def f():\n    return make_row(1)\n",
    must_not_fire=("HC-P010",),
)
_case(
    "p010_returns_dict_literal_clean",
    "def f():\n    return {'a': 1}\n",
    must_not_fire=("HC-P010",),
)
_case(
    "p010_returns_method_call_clean",
    "def f(obj):\n    return obj.build(1)\n",
    must_not_fire=("HC-P010",),
)
_case(
    "p010_bare_return_clean",
    "def f():\n    return\n",
    must_not_fire=("HC-P010",),
)
# A non-TypedDict approved class (Protocol) exercises the non-TypedDict branch of the typeddict scan.
_case(
    "p010_protocol_class_clean",
    "from typing import Protocol\nclass P(Protocol):\n    pass\ndef f():\n    return make_row(1)\n",
    must_not_fire=("HC-P010", "HC-P003"),
)


# ----------------------------------------------------------------- HC-P001 dispatch shapes

_case(
    "p001_dispatch_chain",
    "def f(x):\n    if x == 'a':\n        return 1\n    elif x == 'b':\n        return 2\n    elif x == 'c':\n        return 3\n    return 0\n",
    must_fire=("HC-P001",),
)
_case(
    "p001_too_few_branches",
    "def f(x):\n    if x == 'a':\n        return 1\n    elif x == 'b':\n        return 2\n    return 0\n",
    must_not_fire=("HC-P001",),
)
_case(
    "p001_different_targets",
    "def f(x, y, z):\n    if x == 'a':\n        return 1\n    elif y == 'b':\n        return 2\n    elif z == 'c':\n        return 3\n    return 0\n",
    must_not_fire=("HC-P001",),
)
_case(
    "p001_not_comparison",
    "def f(x):\n    if x:\n        return 1\n    elif x > 1:\n        return 2\n    elif x < 0:\n        return 3\n    return 0\n",
    must_not_fire=("HC-P001",),
)
_case(
    "p001_not_equality_operator",
    "def f(x):\n    if x != 'a':\n        return 1\n    elif x != 'b':\n        return 2\n    elif x != 'c':\n        return 3\n    return 0\n",
    must_not_fire=("HC-P001",),
)
_case(
    "p001_left_not_identifier",
    "def f(x):\n    if 1 == x:\n        return 1\n    elif 2 == x:\n        return 2\n    elif 3 == x:\n        return 3\n    return 0\n",
    must_not_fire=("HC-P001",),
)
_case(
    "p001_single_operand_comparison",
    "def f(x):\n    if (x ==):\n        pass\n",  # syntax error -> HC-SYN; guards _equality_target len<2 elsewhere
    must_fire=("HC-SYN",),
)


# ----------------------------------------------------------------- HC-P011 lifecycle hooks

_case(
    "p011_lifecycle",
    "def setup():\n    addEventListener('click', h)\n",
    must_fire=("HC-P011",),
)
_case(
    "p011_attribute_call_not_hook",
    "def setup():\n    obj.render()\n",
    must_not_fire=("HC-P011",),
)


# ----------------------------------------------------------------- HC-P007 instance state

_case(
    "p007_underscore_instance_state",
    "class C:\n    def __init__(self):\n        self._x = 1\n",
    must_fire=("HC-P007",),
)
_case(
    "p007_public_instance_state_clean",
    "class C:\n    def __init__(self):\n        self.x = 1\n",
    must_not_fire=("HC-P007",),
)
_case(
    "p007_augmented_self_write",
    "class C:\n    def __init__(self):\n        self._x += 1\n",
    must_fire=("HC-P007",),
)
_case(
    "p007_non_init_method_ignored",
    "class C:\n    def go(self):\n        self._x = 1\n",
    must_not_fire=("HC-P007",),
)
_case(
    "p007_non_self_attr_write",
    "class C:\n    def __init__(self, o):\n        o._x = 1\n",
    must_not_fire=("HC-P007",),
)


# ----------------------------------------------------------------- HC-P016 nonlocal mutation

_case(
    "p016_nonlocal_mutated",
    "def outer():\n    total = 0\n    def inner():\n        nonlocal total\n        total = total + 1\n    return inner\n",
    must_fire=("HC-P016",),
)
_case(
    "p016_nonlocal_tuple_target",
    "def outer():\n    a = 0\n    def inner():\n        nonlocal a\n        a, b = 1, 2\n    return inner\n",
    must_fire=("HC-P016",),
)
# A tuple target whose elements do NOT include the captured name (the loop iterates
# without a match), followed by an assignment that does rebind it — exercises the
# tuple-target loop's non-matching iterations and fall-through in _rebinds_name.
_case(
    "p016_tuple_target_then_rebind",
    "def outer():\n    a = 0\n    def inner():\n        nonlocal a\n        b, c = 1, 2\n        a = 5\n    return inner\n",
    must_fire=("HC-P016",),
)
# A tuple target with a non-identifier element (subscript) before the captured name:
# the loop skips the subscript (318 False) then matches the identifier.
_case(
    "p016_tuple_target_mixed_elements",
    "def outer():\n    a = 0\n    d = {}\n    def inner():\n        nonlocal a\n        d[0], a = 1, 2\n    return inner\n",
    must_fire=("HC-P016",),
)
_case(
    "p016_nonlocal_not_mutated",
    "def outer():\n    total = 0\n    def inner():\n        nonlocal total\n        return total\n    return inner\n",
    must_not_fire=("HC-P016",),
)
# An attribute-target assignment (neither a matching identifier nor a tuple target)
# before the real rebind exercises the non-tuple fall-through in _rebinds_name.
_case(
    "p016_attribute_assign_then_rebind",
    "def outer():\n    a = 0\n    obj = O()\n    def inner():\n        nonlocal a\n        obj.field = 1\n        a = 5\n    return inner\n",
    must_fire=("HC-P016",),
)
_case(
    "p016_no_nonlocal",
    "def outer():\n    def inner():\n        x = 1\n        return x\n    return inner\n",
    must_not_fire=("HC-P016",),
)
_case(
    "p016_augmented_nonlocal",
    "def outer():\n    total = 0\n    def inner():\n        nonlocal total\n        total += 1\n    return inner\n",
    must_fire=("HC-P016",),
)


# ----------------------------------------------------------------- HC-P004 / HC008 I/O & state

_case(
    "p004_io_in_non_boundary",
    "def f():\n    open('x')\n",
    must_fire=("HC-P004",),
)
_case(
    "p004_io_in_boundary_clean",
    "from honest_type import boundary\n@boundary\ndef f():\n    open('x')\n",
    must_not_fire=("HC-P004",),
)
_case(
    "p004_io_at_module_level_clean",
    "open('x')\n",
    must_not_fire=("HC-P004",),
)
_case(
    "p004_global_mutable_read",
    "CACHE = {}\nCACHE['a'] = 1\ndef f():\n    return CACHE\n",
    must_fire=("HC-P004",),
)
_case(
    "p004_constant_table_read_clean",
    "TABLE = {'a': 1}\ndef f():\n    return TABLE['a']\n",
    must_not_fire=("HC-P004",),
)
_case(
    "p004_mutated_via_method",
    "ITEMS = []\nITEMS.append(1)\ndef f():\n    return ITEMS\n",
    must_fire=("HC-P004",),
)
_case(
    "p004_mutated_via_reassignment",
    "S = {1}\nS = {2}\ndef f():\n    return S\n",
    must_fire=("HC-P004",),
)
_case(
    "p004_mutated_via_del",
    "D = {'a': 1}\ndel D['a']\ndef f():\n    return D\n",
    must_fire=("HC-P004",),
)
_case(
    "p004_global_read_in_boundary_clean",
    "from honest_type import boundary\nCACHE = {}\nCACHE['a'] = 1\n@boundary\ndef f():\n    return CACHE\n",
    must_not_fire=("HC-P004",),
)
_case(
    "p004_mutable_local_shadow_clean",
    "CACHE = {}\nCACHE['a'] = 1\ndef f():\n    CACHE = {}\n    return CACHE\n",
    must_not_fire=("HC-P004",),
)
# o.CACHE / g(CACHE=1) DO exempt CACHE here. The attribute-name and keyword-argument-name
# uses are name labels, not value loads, so _is_value_load returns False (the now-reachable
# `return False` branches at rules.py 503/505) and HC-P004 does not fire. The only occurrence
# of CACHE in each function is as a label, so no value-load remains to flag.
_case(
    "p004_attribute_and_keyword_occurrence",
    "CACHE = {}\nCACHE['a'] = 1\ndef f(o):\n    return o.CACHE\ndef g(h):\n    return h(CACHE=1)\n",
    must_not_fire=("HC-P004",),
)
_case(
    "p004_for_target_local_clean",
    "CACHE = {}\nCACHE['a'] = 1\ndef f(items):\n    for CACHE in items:\n        pass\n    return CACHE\n",
    must_not_fire=("HC-P004",),
)
# A callee that is not a name path (subscript-call) exercises _dotted_name's "" return
# and _qualified_call_name over a non-name function. No rule fires.
_case(
    "p004_subscript_callee_clean",
    "def f(handlers):\n    return handlers[0]()\n",
    must_not_fire=("HC-P004", "HC-P005"),
)
# A module-level subscript-assign whose base is not a plain identifier (attribute base)
# exercises _subscript_base's non-identifier None return; the dict is still a constant.
_case(
    "p004_attribute_subscript_base_clean",
    "import mod\nTABLE = {'a': 1}\nmod.other['a'] = 1\ndef f():\n    return TABLE['a']\n",
    must_not_fire=("HC-P004",),
)
# A del with a bare-name target (no subscript base -> the base-is-None loop skip) next
# to a real subscript del exercises both sides of the del-target base check.
_case(
    "p004_del_bare_and_subscript",
    "D = {'a': 1}\nE = {'b': 2}\ndel E\ndel D['a']\ndef f():\n    return D\n",
    must_fire=("HC-P004",),
)
# A function whose body has both a for-target identifier and parameter names exercises
# the _local_names parameter and for-loop collection branches while still reading the
# global (different name) so HC-P004 fires.
_case(
    "p004_for_and_params_with_global_read",
    "CACHE = {}\nCACHE['a'] = 1\ndef f(p, q):\n    acc = 0\n    for i in p:\n        acc = acc + i\n    return CACHE\n",
    must_fire=("HC-P004",),
)
# A no-parameter function reading the global exercises the params-is-None / empty path
# of _local_names.
_case(
    "p004_no_params_global_read",
    "CACHE = {}\nCACHE['a'] = 1\ndef f():\n    return CACHE\n",
    must_fire=("HC-P004",),
)
# A tuple for-target (multiple identifiers) and a typed parameter exercise the for-loop
# multi-identifier and parameter-walk branches of _local_names.
_case(
    "p004_tuple_for_target_typed_param",
    "CACHE = {}\nCACHE['a'] = 1\ndef f(p: dict):\n    for k, v in p.items():\n        pass\n    return CACHE\n",
    must_fire=("HC-P004",),
)
# Positional-only / keyword-only separators are parameter children with no identifier:
# the inner param walk completes without binding a name (the no-break loop exit).
_case(
    "p004_param_separators",
    "CACHE = {}\nCACHE['a'] = 1\ndef f(a, /, *, b):\n    return CACHE\n",
    must_fire=("HC-P004",),
)
_case(
    "p008_impure_link_warns",
    "from honest_type import link\n@link(accepts=A, emits=B)\ndef f(x):\n    open('x')\n",
    must_fire=("HC008",),
)
_case(
    "p008_boundary_link_clean",
    "from honest_type import link\n@link(accepts=A, emits=B, boundary=True)\ndef f(x):\n    open('x')\n",
    must_not_fire=("HC008",),
)
_case(
    "p008_pure_link_clean",
    "from honest_type import link\n@link(accepts=A, emits=B)\ndef f(x):\n    return x\n",
    must_not_fire=("HC008",),
)


# ----------------------------------------------------------------- HC-P005 isinstance/type

_case(
    "p005_isinstance_business",
    "def f(x):\n    return isinstance(x, int)\n",
    must_fire=("HC-P005",),
)
_case(
    "p005_isinstance_boundary_clean",
    "from honest_type import boundary\n@boundary\ndef f(x):\n    return isinstance(x, int)\n",
    must_not_fire=("HC-P005",),
)
_case(
    "p005_isinstance_module_level",
    "x = type(5)\n",
    must_fire=("HC-P005",),
)


# ----------------------------------------------------------------- HC-P006 cache evidence

_case(
    "p006_cache_unprofiled",
    "from functools import lru_cache\n@lru_cache\ndef f(x):\n    return x\n",
    must_fire=("HC-P006",),
)
_case(
    "p006_cache_profiled_decorator_clean",
    "from functools import lru_cache\n@profiled\n@lru_cache\ndef f(x):\n    return x\n",
    must_not_fire=("HC-P006",),
)
_case(
    "p006_cache_profiled_comment_preceding_clean",
    "# honest: profiled\n@lru_cache\ndef f(x):\n    return x\n",
    must_not_fire=("HC-P006",),
)
_case(
    "p006_cache_profiled_comment_inside_clean",
    "@lru_cache\n# honest: profiled\ndef f(x):\n    return x\n",
    must_not_fire=("HC-P006",),
)
# A non-profiled comment closer than the profiled one forces the prev_sibling loop to
# advance past the first comment before finding the evidence.
_case(
    "p006_profiled_comment_after_other_comment_clean",
    "# honest: profiled\n# unrelated note\n@lru_cache\ndef f(x):\n    return x\n",
    must_not_fire=("HC-P006",),
)
_case(
    "p006_no_cache_clean",
    "@staticmethod\ndef f(x):\n    return x\n",
    must_not_fire=("HC-P006",),
)


# ----------------------------------------------------------------- HC007 empty chain

_case(
    "hc007_empty_chain",
    "from honest_type import chain\nc = chain()\n",
    must_fire=("HC007",),
)
_case(
    "hc007_anonymous_empty_chain",
    "from honest_type import chain\nchain()\n",
    must_fire=("HC007",),
)
_case(
    "hc007_non_empty_chain_clean",
    "from honest_type import chain\ndef a():\n    pass\nc = chain(a)\n",
    must_not_fire=("HC007",),
)


# ----------------------------------------------------------------- HC003 overlap / predicate

_case(
    "hc003_set_overlap",
    "from honest_type import vocabulary\nV = vocabulary({'a': {'x', 'y'}, 'b': {'y', 'z'}})\n",
    must_fire=("HC003",),
)
_case(
    "hc003_set_disjoint_clean",
    "from honest_type import vocabulary\nV = vocabulary({'a': {'x'}, 'b': {'y'}})\n",
    must_not_fire=("HC003",),
)
_case(
    "hc003_predicate_pair_info",
    "from honest_type import vocabulary, predicate\nV = vocabulary({'a': predicate(p1), 'b': predicate(p2)})\n",
    must_fire=("HC003",),
)
# A Set type beside a predicate type may overlap on a Set value, but the static linter cannot
# evaluate the predicate; it emits an info pointing to honest-test (section 1.1, 4.1).
_case(
    "hc003_set_predicate_info",
    "from honest_type import vocabulary, predicate\nV = vocabulary({'a': {'x'}, 'b': predicate(p)})\n",
    must_fire=("HC003",),
)


# ----------------------------------------------------------------- HC004 / HC005 binding pairings

_case(
    "hc004_unbound_type",
    "from honest_type import vocabulary, binding, link\n"
    "V = vocabulary({'a': {'x'}, 'b': {'y'}})\n"
    "B = binding({'a': 'slot1'})\n"
    "@link(accepts=V, binds=B)\n"
    "def f(x):\n    return x\n",
    must_fire=("HC004",),
)
_case(
    "hc004_all_bound_clean",
    "from honest_type import vocabulary, binding, link\n"
    "V = vocabulary({'a': {'x'}})\n"
    "B = binding({'a': 'slot1'})\n"
    "@link(accepts=V, binds=B)\n"
    "def f(x):\n    return x\n",
    must_not_fire=("HC004",),
)
_case(
    "hc005_binding_unknown_type",
    "from honest_type import vocabulary, binding, link\n"
    "V = vocabulary({'a': {'x'}})\n"
    "B = binding({'a': 'slot1', 'ghost': 'slot2'})\n"
    "@link(accepts=V, binds=B)\n"
    "def f(x):\n    return x\n",
    must_fire=("HC005",),
)
_case(
    "hc004_classify_positional_pairing",
    "from honest_type import vocabulary, binding, classify\n"
    "V = vocabulary({'a': {'x'}, 'b': {'y'}})\n"
    "B = binding({'a': 'slot1'})\n"
    "result = classify(token, V, B)\n",
    must_fire=("HC004",),
)
# A link pairing names that are not defined vocabularies/bindings: the pairing exists
# but vocab_var/binding_var miss the dicts, exercising the not-found continue in
# HC004/HC005/HC-P014.
_case(
    "hc004_undefined_pairing_clean",
    "from honest_type import link\n"
    "@link(accepts=NotAVocab, binds=NotABinding)\n"
    "def f(x):\n    return x\n",
    must_not_fire=("HC004", "HC005", "HC-P014"),
)
# Two links pairing the SAME vocabulary and binding (same unbound type, same invalid
# binding entry, same shared recognizer) exercise the `seen` dedup `continue` in
# HC004/HC005/HC-P014 — the second pairing is skipped.
_case(
    "hc004_005_p014_duplicate_pairing_dedup",
    "from honest_type import vocabulary, binding, link\n"
    "V = vocabulary({'a': {'x'}, 'b': {'x'}, 'c': {'q'}})\n"
    "B = binding({'a': 'slot1', 'b': 'slot2', 'ghost': 'slotg'})\n"
    "@link(accepts=V, binds=B)\n"
    "def f(x):\n    return x\n"
    "@link(accepts=V, binds=B)\n"
    "def g(x):\n    return x\n",
    must_fire=("HC004", "HC005", "HC-P014"),
)
_case(
    "hc004_classify_keyword_pairing",
    "from honest_type import vocabulary, binding, classify\n"
    "V = vocabulary({'a': {'x'}, 'b': {'y'}})\n"
    "B = binding({'a': 'slot1'})\n"
    "result = classify(token, vocab=V, bind=B)\n",
    must_fire=("HC004",),
)
# classify with a positional vocab but a keyword bind: vocab resolved positionally,
# binding already present (the binding-is-not-None skip of the positional fill).
_case(
    "hc004_classify_positional_vocab_keyword_bind",
    "from honest_type import vocabulary, binding, classify\n"
    "V = vocabulary({'a': {'x'}, 'b': {'y'}})\n"
    "B = binding({'a': 'slot1'})\n"
    "result = classify(token, V, bind=B)\n",
    must_fire=("HC004",),
)
# classify whose positional vocab slot is not an identifier (a call) fails the final
# identifier check — no pairing recorded.
_case(
    "declgraph_classify_nonidentifier_positional_clean",
    "from honest_type import vocabulary, binding, classify\n"
    "result = classify(token, make_vocab(), make_binding())\n",
    must_not_fire=("HC-SYN", "HC004"),
)
# classify with vocab supplied by keyword but binding entirely absent: the positional-fill
# block is entered (binding is None) but the vocab-fill is skipped (vocab not None), and
# there are too few positionals to fill the binding. No identifier pairing -> no fire.
_case(
    "declgraph_classify_vocab_only_clean",
    "from honest_type import vocabulary, binding, classify\n"
    "V = vocabulary({'a': {'x'}})\n"
    "result = classify(token, vocab=V)\n",
    must_not_fire=("HC-SYN", "HC004"),
)
# An anonymous binding (not assigned), a binding with no dict argument, and a binding dict
# carrying a ** spread and a non-string key/value exercise extract_bindings' name-None,
# no-dict, non-pair, and non-string-entry skips.
_case(
    "declgraph_binding_edges_clean",
    "from honest_type import binding\n"
    "extra = {'g': 'sg'}\n"
    "binding({'a': 'slot1'})\n"
    "B0 = binding()\n"
    "B1 = binding({'a': 'slot1', 5: 'slotn', 'b': 6, **extra})\n",
    must_not_fire=("HC-SYN",),
)


# ----------------------------------------------------------------- HC-P013 unbounded routing key

# A database routing key (db_id/tenant_id/credential) bound to a predicate recognizer is unbounded:
# an arbitrary identifier reaches the pool layer. The vocabulary must be the whitelist (a bounded Set).
_case(
    "p013_predicate_db_id",
    "from honest_type import vocabulary, binding, link, predicate\n"
    "V = vocabulary({'db': predicate(p)})\n"
    "B = binding({'db': 'db_id'})\n"
    "@link(accepts=V, binds=B)\n"
    "def f(x):\n    return x\n",
    must_fire=("HC-P013",),
)
# tenant_id and credential are routing keys too; a predicate behind either fires.
_case(
    "p013_predicate_tenant_and_credential",
    "from honest_type import vocabulary, binding, link, predicate\n"
    "V = vocabulary({'t': predicate(p), 'c': predicate(q)})\n"
    "B = binding({'t': 'tenant_id', 'c': 'credential'})\n"
    "@link(accepts=V, binds=B)\n"
    "def f(x):\n    return x\n",
    must_fire=("HC-P013",),
)
# A bounded Set behind a routing key is the whitelist — clean.
_case(
    "p013_bounded_set_clean",
    "from honest_type import vocabulary, binding, link\n"
    "V = vocabulary({'db': {'users_db', 'orders_db'}})\n"
    "B = binding({'db': 'db_id'})\n"
    "@link(accepts=V, binds=B)\n"
    "def f(x):\n    return x\n",
    must_not_fire=("HC-P013",),
)
# A predicate behind a NON-routing slot is fine — only routing keys are whitelisted.
_case(
    "p013_predicate_non_routing_slot_clean",
    "from honest_type import vocabulary, binding, link, predicate\n"
    "V = vocabulary({'amt': predicate(p)})\n"
    "B = binding({'amt': 'amount'})\n"
    "@link(accepts=V, binds=B)\n"
    "def f(x):\n    return x\n",
    must_not_fire=("HC-P013",),
)
# A ref recognizer behind a routing key is not a predicate at this site — not flagged here.
_case(
    "p013_ref_routing_key_clean",
    "from honest_type import vocabulary, binding, link\n"
    "V = vocabulary({'db': other_recognizer})\n"
    "B = binding({'db': 'db_id'})\n"
    "@link(accepts=V, binds=B)\n"
    "def f(x):\n    return x\n",
    must_not_fire=("HC-P013",),
)
# A routing slot bound to a type absent from the vocabulary has no recognizer to inspect — no fire.
_case(
    "p013_routing_key_unknown_type_clean",
    "from honest_type import vocabulary, binding, link\n"
    "V = vocabulary({'db': {'x'}})\n"
    "B = binding({'ghost': 'db_id'})\n"
    "@link(accepts=V, binds=B)\n"
    "def f(x):\n    return x\n",
    must_not_fire=("HC-P013",),
)
# Two links pairing the SAME vocabulary and binding exercise the seen-dedup continue.
_case(
    "p013_duplicate_pairing_dedup",
    "from honest_type import vocabulary, binding, link, predicate\n"
    "V = vocabulary({'db': predicate(p)})\n"
    "B = binding({'db': 'db_id'})\n"
    "@link(accepts=V, binds=B)\n"
    "def f(x):\n    return x\n"
    "@link(accepts=V, binds=B)\n"
    "def g(x):\n    return x\n",
    must_fire=("HC-P013",),
)
# A pairing whose vocabulary and binding are undefined misses the dicts — the not-found continue.
_case(
    "p013_undefined_pairing_clean",
    "from honest_type import link\n"
    "@link(accepts=NoVocab, binds=NoBinding)\n"
    "def f(x):\n    return x\n",
    must_not_fire=("HC-P013",),
)


# ----------------------------------------------------------------- HC-P014 shared recognizer

_case(
    "p014_shared_set_recognizer",
    "from honest_type import vocabulary, binding, link\n"
    "V = vocabulary({'a': {'x'}, 'b': {'x'}})\n"
    "B = binding({'a': 'slot1', 'b': 'slot2'})\n"
    "@link(accepts=V, binds=B)\n"
    "def f(x):\n    return x\n",
    must_fire=("HC-P014",),
)
_case(
    "p014_shared_ref_recognizer",
    "from honest_type import vocabulary, binding, link\n"
    "V = vocabulary({'a': rec, 'b': rec})\n"
    "B = binding({'a': 'slot1', 'b': 'slot2'})\n"
    "@link(accepts=V, binds=B)\n"
    "def f(x):\n    return x\n",
    must_fire=("HC-P014",),
)
_case(
    "p014_same_slot_clean",
    "from honest_type import vocabulary, binding, link\n"
    "V = vocabulary({'a': {'x'}, 'b': {'x'}})\n"
    "B = binding({'a': 'slot1', 'b': 'slot1'})\n"
    "@link(accepts=V, binds=B)\n"
    "def f(x):\n    return x\n",
    must_not_fire=("HC-P014",),
)
_case(
    "p014_predicate_opaque_clean",
    "from honest_type import vocabulary, binding, link, predicate\n"
    "V = vocabulary({'a': predicate(p), 'b': predicate(p)})\n"
    "B = binding({'a': 'slot1', 'b': 'slot2'})\n"
    "@link(accepts=V, binds=B)\n"
    "def f(x):\n    return x\n",
    must_not_fire=("HC-P014",),
)


# ----------------------------------------------------------------- HC009 risky predicate

_case(
    "hc009_int_call",
    "from honest_type import vocabulary, predicate\nV = vocabulary({'a': predicate(lambda s: int(s) > 0)})\n",
    must_fire=("HC009",),
)
_case(
    "hc009_subscript",
    "from honest_type import vocabulary, predicate\nV = vocabulary({'a': predicate(lambda s: s[0] == 'x')})\n",
    must_fire=("HC009",),
)
_case(
    "hc009_division",
    "from honest_type import vocabulary, predicate\nV = vocabulary({'a': predicate(lambda s: 1 / s == 2)})\n",
    must_fire=("HC009",),
)
_case(
    "hc009_safe_predicate_clean",
    "from honest_type import vocabulary, predicate\nV = vocabulary({'a': predicate(lambda s: s in {'x'})})\n",
    must_not_fire=("HC009",),
)


# ----------------------------------------------------------------- HC011 catch-all predicate

_case(
    "hc011_predicate_info",
    "from honest_type import vocabulary, predicate\nV = vocabulary({'a': predicate(p)})\n",
    must_fire=("HC011",),
)
_case(
    "hc011_set_clean",
    "from honest_type import vocabulary\nV = vocabulary({'a': {'x'}})\n",
    must_not_fire=("HC011",),
)


# ----------------------------------------------------------------- HC-A001 / HC-A002 auth

_case(
    "a001_no_provider",
    "from honest_type import link\n@link(authorizes=True)\ndef f(x):\n    return x\n",
    must_fire=("HC-A001",),
)
_case(
    "a001_provider_registered_clean",
    "from honest_type import link\n"
    "@link(authorizes=True)\n"
    "def f(x):\n    return session_actor\n"
    "p = AuthProvider(derivation_expression=GuardExpressionTemplate.lookup('session_actor'))\n"
    "register_auth_provider(p)\n",
    must_not_fire=("HC-A001",),
)
_case(
    "a001_no_authorizing_links_clean",
    "from honest_type import link\n@link(accepts=A)\ndef f(x):\n    return x\n",
    must_not_fire=("HC-A001",),
)
_case(
    "a002_missing_derivation_reference",
    "from honest_type import link\n"
    "@link(authorizes=True)\n"
    "def f(x):\n    return x\n"
    "p = AuthProvider(derivation_expression=GuardExpressionTemplate.lookup('session_actor'))\n"
    "register_auth_provider(p)\n",
    must_fire=("HC-A002",),
)
_case(
    "a002_literal_provider_clean",
    "from honest_type import link\n"
    "@link(authorizes=True)\n"
    "def f(x):\n    return x\n"
    "p = AuthProvider(derivation_expression=GuardExpressionTemplate.literal('nobody'))\n"
    "register_auth_provider(p)\n",
    must_not_fire=("HC-A002", "HC-A001"),
)
_case(
    "a002_provider_no_derivation_kw_clean",
    "from honest_type import link\n"
    "@link(authorizes=True)\n"
    "def f(x):\n    return x\n"
    "p = AuthProvider()\n"
    "register_auth_provider(p)\n",
    must_not_fire=("HC-A002",),
)
_case(
    "a001_provider_not_inline_clean",
    "from honest_type import link\n"
    "@link(authorizes=True)\n"
    "def f(x):\n    return x\n"
    "register_auth_provider(some_provider)\n",
    must_not_fire=("HC-A001",),
)


# ----------------------------------------------------------------- HC-OR001 / HC-OR003

_case(
    "or001_orchestrator_calls_orchestrator",
    "from honest_type import orchestrator\n"
    "@orchestrator\ndef a():\n    b()\n"
    "@orchestrator\ndef b():\n    pass\n",
    must_fire=("HC-OR001",),
)
_case(
    "or001_orchestrator_calls_helper_clean",
    "from honest_type import orchestrator\n"
    "@orchestrator\ndef a():\n    helper()\n"
    "def helper():\n    pass\n",
    must_not_fire=("HC-OR001",),
)
_case(
    "or003_shared_run",
    "from honest_type import orchestrator\n"
    "@orchestrator\ndef a():\n    step1()\n    step2()\n    step3()\n"
    "@orchestrator\ndef b():\n    step1()\n    step2()\n    step3()\n",
    must_fire=("HC-OR003",),
)
_case(
    "or003_short_run_clean",
    "from honest_type import orchestrator\n"
    "@orchestrator\ndef a():\n    step1()\n    step2()\n"
    "@orchestrator\ndef b():\n    step1()\n    step2()\n",
    must_not_fire=("HC-OR003",),
)


# ----------------------------------------------------------------- HC-P017 HTTP output

_case(
    "p017_http_output_no_link",
    "def handler(req):\n    return JSONResponse({'ok': True})\n",
    must_fire=("HC-P017",),
)
_case(
    "p017_http_output_link_with_emits_clean",
    "from honest_type import link\n@link(emits=Resp)\ndef handler(req):\n    return JSONResponse({'ok': True})\n",
    must_not_fire=("HC-P017",),
)
_case(
    "p017_no_http_output_clean",
    "def handler(req):\n    return {'ok': True}\n",
    must_not_fire=("HC-P017",),
)


# ----------------------------------------------------------------- HC001 / HC002 chain wiring

_case(
    "hc001_link_without_vocabulary",
    "from honest_type import chain\ndef step(x):\n    return x\nc = chain(step)\n",
    must_fire=("HC001",),
)
_case(
    "hc001_external_reference_clean",
    "from honest_type import chain\nc = chain(external_step)\n",
    must_not_fire=("HC001",),
)
_case(
    "hc002_type_mismatch",
    "from honest_type import vocabulary, link, chain\n"
    "A = vocabulary({'a': {'x'}})\n"
    "B = vocabulary({'b': {'y'}})\n"
    "@link(accepts=A, emits=A)\n"
    "def first(x):\n    return x\n"
    "@link(accepts=B, emits=B)\n"
    "def second(x):\n    return x\n"
    "c = chain(first, second)\n",
    must_fire=("HC002",),
)
_case(
    "hc002_compatible_clean",
    "from honest_type import vocabulary, link, chain\n"
    "A = vocabulary({'a': {'x'}})\n"
    "@link(accepts=A, emits=A)\n"
    "def first(x):\n    return x\n"
    "@link(accepts=A, emits=A)\n"
    "def second(x):\n    return x\n"
    "c = chain(first, second)\n",
    must_not_fire=("HC002",),
)
# A predecessor that emits an empty vocabulary makes `emits` empty, so HC002's per-edge
# check short-circuits (rules.py 1419-1420 `if not emits ... continue`): a link that emits
# nothing cannot under-supply its successor, so no mismatch is reported.
_case(
    "hc002_empty_emits_clean",
    "from honest_type import vocabulary, link, chain\n"
    "A = vocabulary({'a': {'x'}})\n"
    "E = vocabulary({})\n"
    "@link(accepts=A, emits=E)\n"
    "def first(x):\n    return x\n"
    "@link(accepts=A, emits=A)\n"
    "def second(x):\n    return x\n"
    "c = chain(first, second)\n",
    must_not_fire=("HC002",),
)


# ----------------------------------------------------------------- HC006 composed types

_case(
    "hc006_requires_unknown",
    "from honest_type import vocabulary, composed\n"
    "V = vocabulary({'a': {'x'}}, composed_types=[composed('combo', requires={'ghost': 1})])\n",
    must_fire=("HC006",),
)
_case(
    "hc006_captures_unknown",
    "from honest_type import vocabulary, composed\n"
    "V = vocabulary({'a': {'x'}}, composed_types=[composed('combo', captures='ghost')])\n",
    must_fire=("HC006",),
)
_case(
    "hc006_captures_maybe_wrapped_unknown",
    "from honest_type import vocabulary, composed, maybe\n"
    "V = vocabulary({'a': {'x'}}, composed_types=[composed('combo', captures=maybe('ghost'))])\n",
    must_fire=("HC006",),
)
_case(
    "hc006_known_clean",
    "from honest_type import vocabulary, composed\n"
    "V = vocabulary({'a': {'x'}}, composed_types=[composed('combo', requires={'a': 1}, captures='a')])\n",
    must_not_fire=("HC006",),
)
_case(
    "hc006_composed_name_keyword",
    "from honest_type import vocabulary, composed\n"
    "V = vocabulary({'a': {'x'}}, composed_types=[composed(name='combo', requires={'ghost': 1})])\n",
    must_fire=("HC006",),
)


# ----------------------------------------------------------------- HC010 phantom emission

_case(
    "hc010_phantom_emit",
    "from honest_type import vocabulary, binding, link\n"
    "A = vocabulary({'a': {'x'}})\n"
    "B = vocabulary({'a': {'x'}, 'b': {'y'}})\n"
    "Bind = binding({'b': 'slot_b'})\n"
    "@link(accepts=A, emits=B, binds=Bind)\n"
    "def f(x):\n    return x\n",
    must_fire=("HC010",),
)
_case(
    "hc010_produced_clean",
    "from honest_type import vocabulary, binding, link\n"
    "A = vocabulary({'a': {'x'}})\n"
    "B = vocabulary({'a': {'x'}, 'b': {'y'}})\n"
    "Bind = binding({'b': 'slot_b'})\n"
    "@link(accepts=A, emits=B, binds=Bind)\n"
    "def f(x):\n    x['slot_b'] = 1\n    return x\n",
    must_not_fire=("HC010",),
)
_case(
    "hc010_no_emits_clean",
    "from honest_type import vocabulary, link\n"
    "A = vocabulary({'a': {'x'}})\n"
    "@link(accepts=A)\n"
    "def f(x):\n    return x\n",
    must_not_fire=("HC010",),
)
_case(
    "hc010_no_binding_clean",
    "from honest_type import vocabulary, link\n"
    "A = vocabulary({'a': {'x'}})\n"
    "B = vocabulary({'a': {'x'}, 'b': {'y'}})\n"
    "@link(accepts=A, emits=B)\n"
    "def f(x):\n    return x\n",
    must_not_fire=("HC010",),
)
_case(
    "hc010_produced_via_dict_literal_clean",
    "from honest_type import vocabulary, binding, link\n"
    "A = vocabulary({'a': {'x'}})\n"
    "B = vocabulary({'a': {'x'}, 'b': {'y'}})\n"
    "Bind = binding({'b': 'slot_b'})\n"
    "@link(accepts=A, emits=B, binds=Bind)\n"
    "def f(x):\n    return {'slot_b': 1}\n",
    must_not_fire=("HC010",),
)
# A link body whose dict literal has a non-string key and a ** spread (non-pair child),
# plus a plain (non-subscript) assignment, exercises the assignment-not-subscript skip
# and the dict non-pair / non-string-key branches of _produced_slot_keys while the slot
# is still produced via subscript-assign (so HC010 stays silent).
_case(
    "hc010_produced_mixed_body_clean",
    "from honest_type import vocabulary, binding, link\n"
    "A = vocabulary({'a': {'x'}})\n"
    "B = vocabulary({'a': {'x'}, 'b': {'y'}})\n"
    "Bind = binding({'b': 'slot_b'})\n"
    "@link(accepts=A, emits=B, binds=Bind)\n"
    "def f(x):\n"
    "    tmp = 1\n"
    "    meta = {99: 'n', **x}\n"
    "    x['slot_b'] = tmp\n"
    "    return x\n",
    must_not_fire=("HC010",),
)


# ----------------------------------------------------------------- HC-P002 try/except

_case(
    "p002_except_in_business",
    "def f():\n    try:\n        do()\n    except ValueError:\n        pass\n",
    must_fire=("HC-P002",),
)
_case(
    "p002_finally_only_clean",
    "def f():\n    try:\n        do()\n    finally:\n        cleanup()\n",
    must_not_fire=("HC-P002",),
)
_case(
    "p002_except_in_boundary_clean",
    "from honest_type import boundary\n@boundary\ndef f():\n    try:\n        do()\n    except ValueError:\n        pass\n",
    must_not_fire=("HC-P002",),
)
_case(
    "p002_except_module_level_clean",
    "try:\n    do()\nexcept ValueError:\n    pass\n",
    must_not_fire=("HC-P002",),
)


# ----------------------------------------------------------------- HC-R001 orphan function

_case(
    "r001_orphan_function",
    "from honest_type import link\n@link(accepts=A)\ndef used():\n    return 1\ndef orphan():\n    return 2\n",
    must_fire=("HC-R001",),
)
_case(
    "r001_reachable_helper_clean",
    "from honest_type import link\n@link(accepts=A)\ndef used():\n    return helper()\ndef helper():\n    return 1\n",
    must_not_fire=("HC-R001",),
)
_case(
    "r001_no_roles_clean",
    "def a():\n    return 1\ndef b():\n    return 2\n",
    must_not_fire=("HC-R001",),
)


# ----------------------------------------------------------------- state machines

_case(
    "sm01_sm02_unknown_state_event",
    "from honest_type import state_machine, vocabulary\n"
    "m = state_machine("
    "states=vocabulary({'s': {'open', 'closed'}}), "
    "events=vocabulary({'e': {'shut'}}), "
    "initial='open', terminal=['closed'], "
    "transitions={('bad', 'badev'): 'closed'})\n",
    must_fire=("HC-SM01", "HC-SM02"),
)
_case(
    "sm05_initial_not_in_states",
    "from honest_type import state_machine, vocabulary\n"
    "m = state_machine("
    "states=vocabulary({'s': {'open', 'closed'}}), "
    "events=vocabulary({'e': {'shut'}}), "
    "initial='ghost', terminal=['closed'], "
    "transitions={('open', 'shut'): 'closed'})\n",
    must_fire=("HC-SM05",),
)
_case(
    "sm03_sm04_unreachable_dead",
    "from honest_type import state_machine, vocabulary\n"
    "m = state_machine("
    "states=vocabulary({'s': {'open', 'closed', 'island'}}), "
    "events=vocabulary({'e': {'shut'}}), "
    "initial='open', terminal=['closed'], "
    "transitions={('open', 'shut'): 'closed'})\n",
    must_fire=("HC-SM03", "HC-SM04"),
)
_case(
    "sm_clean",
    "from honest_type import state_machine, vocabulary\n"
    "m = state_machine("
    "states=vocabulary({'s': {'open', 'closed'}}), "
    "events=vocabulary({'e': {'shut'}}), "
    "initial='open', terminal=['closed'], "
    "transitions={('open', 'shut'): 'closed'})\n",
    must_not_fire=("HC-SM01", "HC-SM02", "HC-SM03", "HC-SM04", "HC-SM05"),
)
_case(
    "sm_no_states_clean",
    "from honest_type import state_machine\n"
    "m = state_machine(initial='open', transitions={('open', 'shut'): 'closed'})\n",
    must_not_fire=("HC-SM01", "HC-SM03", "HC-SM04", "HC-SM05"),
)
_case(
    "sm_no_initial_reachability_skip",
    "from honest_type import state_machine, vocabulary\n"
    "m = state_machine("
    "states=vocabulary({'s': {'open', 'closed'}}), "
    "events=vocabulary({'e': {'shut'}}), "
    "terminal=['closed'], "
    "transitions={('open', 'shut'): 'closed'})\n",
    must_not_fire=("HC-SM03", "HC-SM05"),
)


# ----------------------------------------------------------------- aliased imports (declgraph 3.3)

_case(
    "alias_from_import_as",
    "from honest_type import chain as ch\nc = ch()\n",
    must_fire=("HC007",),
)
_case(
    "alias_module_import",
    "import honest_type\nc = honest_type.chain()\n",
    must_fire=("HC007",),
)
_case(
    "alias_module_import_as",
    "import honest_type as ht\nc = ht.chain()\n",
    must_fire=("HC007",),
)
# A from-import of a non-honest-type name (alias path with a name not in the vocabulary),
# a non-honest module import-as, and a plain os import exercise resolve_aliases's
# skip branches.
_case(
    "alias_unrelated_imports_clean",
    "from honest_type import nonexistent as nx\nimport os\nimport os as o\n",
    must_not_fire=("HC007", "HC003"),
)


# ----------------------------------------------------------------- declgraph node shapes

# An empty-string type key exercises string_value's "" return (a string node with no
# string_content child); a non-string (integer) key exercises the type_name-is-None skip;
# a ** spread is a non-pair dict child. The vocabulary is still well-formed enough to run.
_case(
    "declgraph_vocab_edge_keys_clean",
    "from honest_type import vocabulary\n"
    "extra = {'z': {'q'}}\n"
    "V = vocabulary({'': {'x'}, 'b': {'y'}, **extra})\n",
    must_not_fire=("HC-SYN",),
)
_case(
    "declgraph_vocab_integer_key_clean",
    "from honest_type import vocabulary\n"
    "V = vocabulary({42: {'x'}, 'b': {'y'}})\n",
    must_not_fire=("HC-SYN",),
)
# A vocabulary assigned to a tuple target (assigned_name's non-identifier-left path) and
# build_vocabulary_definitions' non-identifier-left skip.
_case(
    "declgraph_tuple_assigned_chain",
    "from honest_type import chain\na, b = chain(), 1\n",
    must_fire=("HC007",),
)
# An attribute-target chain assignment also exercises assigned_name's non-identifier left.
_case(
    "declgraph_attribute_assigned_chain",
    "from honest_type import chain\nholder.c = chain()\n",
    must_fire=("HC007",),
)
# A composed_types list with a non-call element (a bare string) and a non-composed call
# exercise the element-not-call and not-composed skips; a composed with a non-string
# (integer) requires key and a maybe()-wrapped capture exercise the requires/capture
# unwrap branches.
_case(
    "declgraph_composed_edges",
    "from honest_type import vocabulary, composed, maybe\n"
    "extra_req = {'a': 1}\n"
    "V = vocabulary({'a': {'x'}}, composed_types=["
    "'not_a_call', other_call(), "
    "composed('combo', requires={'a': 1, 7: 2, **extra_req}, captures=maybe('a'))])\n",
    must_not_fire=("HC-SYN",),
)
# A maybe()-wrapped capture whose inner call has no string argument exercises the
# capture-unwrap loop's no-string fall-through (captures stays None).
_case(
    "declgraph_composed_maybe_no_string",
    "from honest_type import vocabulary, composed, maybe\n"
    "V = vocabulary({'a': {'x'}}, composed_types=[composed('combo', requires={'a': 1}, captures=maybe(dynamic))])\n",
    must_not_fire=("HC-SYN",),
)
# A vocabulary-merge expression (A | B), a parenthesized vocabulary, and an inline
# vocabulary call as an accepts= expression exercise vocab_expr_type_names' binary,
# parenthesized, and inline-call branches.
_case(
    "declgraph_vocab_merge_paren_inline",
    "from honest_type import vocabulary, link\n"
    "A = vocabulary({'a': {'x'}})\n"
    "B = vocabulary({'b': {'y'}})\n"
    "@link(accepts=(A) | B, emits=vocabulary({'c': {'z'}}))\n"
    "def f(x):\n    return x\n",
    must_not_fire=("HC-SYN",),
)
# A function carrying a non-link decorator before any role/link check exercises
# link_decorator_call's non-link-decorator continue and function_role's attribute-form
# decorator (name="") branch.
_case(
    "declgraph_nonlink_and_attribute_decorators_clean",
    "import functools\n@functools.wraps\n@staticmethod\ndef f(x):\n    return x\n",
    must_not_fire=("HC-SYN", "HC-R001"),
)
# A call-form decorator whose callee is NOT 'link' (an attribute-callee call like
# @app.route('/x')) exercises link_decorator_call's call-decorator-but-not-link continue.
_case(
    "declgraph_call_decorator_not_link_clean",
    "@app.route('/x')\ndef f(x):\n    return x\n",
    must_not_fire=("HC-SYN",),
)
# A chain call with a non-identifier argument (a string) exercises the non-identifier
# argument skip in extract_chains; the chain still has one real link so HC007 is silent.
_case(
    "declgraph_chain_mixed_args_clean",
    "from honest_type import chain\ndef step(x):\n    return x\nc = chain(step, 'label')\n",
    must_not_fire=("HC007",),
)
# A state machine whose states vocabulary uses a predicate recognizer (non-set) exercises
# vocabulary_members' non-set skip; transition keys that are not 2-tuples / non-string and
# a ** spread in the transitions dict exercise transition_table's skip branches.
_case(
    "declgraph_sm_predicate_states_and_bad_transitions_clean",
    "from honest_type import state_machine, vocabulary, predicate\n"
    "more = {('x', 'y'): 'z'}\n"
    "m = state_machine("
    "states=vocabulary({'s': predicate(p)}), "
    "events=vocabulary({'e': {'go'}}), "
    "transitions={('a',): 'b', 'flat': 'c', (1, 2): 'd', **more})\n",
    must_not_fire=("HC-SYN",),
)
# An auth provider registered with a non-identifier argument, an AuthProvider lookup with
# a non-string first arg, and a lookup-derivation provider plus a non-AuthProvider call
# assignment and an unrelated module assignment exercise the provider-resolution skips.
# Two registrations: one provider var (q) is assigned to a non-AuthProvider call (the
# fn-not-AuthProvider continue), plus a non-identifier register arg ('literal_arg'), a
# non-call module assignment (count), and an unrelated call assignment (noise). The real
# AuthProvider (p) still resolves, so HC-A001 stays silent.
_case(
    "declgraph_auth_provider_resolution_clean",
    "from honest_type import link\n"
    "@link(authorizes=True)\n"
    "def f(x):\n    return session_actor\n"
    "count = 5\n"
    "noise = compute()\n"
    "q = NotAuthProvider()\n"
    "p = AuthProvider(derivation_expression=GuardExpressionTemplate.lookup('session_actor'))\n"
    "register_auth_provider(q, 'literal_arg')\n"
    "register_auth_provider(p)\n",
    must_not_fire=("HC-A001",),
)
# A lookup-derivation whose argument list has a non-string before the string exercises
# _derivation_signature's non-string-arg continue; a literal(...) derivation exercises the
# method != 'lookup' early return.
_case(
    "declgraph_auth_lookup_nonstring_then_string_clean",
    "from honest_type import link\n"
    "@link(authorizes=True)\n"
    "def f(x):\n    return session_actor\n"
    "p = AuthProvider(derivation_expression=GuardExpressionTemplate.lookup(prefix, 'session_actor'))\n"
    "register_auth_provider(p)\n",
    must_not_fire=("HC-A001",),
)
# A lookup-derivation with NO string argument at all exercises _derivation_signature's
# loop-exhausted '' return. With an empty signature, authorizing links need no reference,
# so HC-A002 stays silent.
_case(
    "declgraph_auth_lookup_no_string_clean",
    "from honest_type import link\n"
    "@link(authorizes=True)\n"
    "def f(x):\n    return x\n"
    "p = AuthProvider(derivation_expression=GuardExpressionTemplate.lookup(dynamic))\n"
    "register_auth_provider(p)\n",
    must_not_fire=("HC-A002",),
)


# ----------------------------------------------------------------- HC-SYN

_case(
    "syntax_error",
    "def (:\n    pass\n",
    must_fire=("HC-SYN",),
)


# ----------------------------------------------------------------- direct-call probes

def _probe_internal_helpers() -> list[str]:
    """Branches in pure declgraph helpers that no check_source path reaches.

    Mirrors laws_hc.py's pattern of calling internal helpers directly with crafted
    inputs. These are defensive return paths (a non-string node to string_value, a
    non-list node to string_list, a non-dictionary to transition_table, a vocabulary
    expression that is neither set/predicate/ref, a non-call derivation node) that are
    unreachable through the registered rule funnel but are honest data-in/data-out
    contracts worth pinning.
    """
    bad: list[str] = []

    src_b = "x = 5\n".encode()
    root = parse_python(src_b).root_node
    integer = next(n for n in _w(root) if n.type == "integer")
    # string_value of a non-string node -> None.
    if string_value(integer, src_b) is not None:
        bad.append("string_value(non-string) should be None")
    # string_list of a non-list node -> [].
    if string_list(integer, src_b) != []:
        bad.append("string_list(non-list) should be []")
    if string_list(None, src_b) != []:
        bad.append("string_list(None) should be []")
    # transition_table of a non-dictionary -> [].
    if transition_table(integer, src_b) != []:
        bad.append("transition_table(non-dict) should be []")
    if transition_table(None, src_b) != []:
        bad.append("transition_table(None) should be []")

    # _derivation_signature: non-call node -> ''.
    if _derivation_signature(integer, src_b) != "":
        bad.append("_derivation_signature(non-call) should be ''")

    # _is_value_load: the parent-is-None path returns True. The root node has no parent.
    if _is_value_load(root) is not True:
        bad.append("_is_value_load(parentless node) should be True")
    # An attribute-name identifier (`o.attr`) and a keyword-argument-name identifier
    # (`g(name=1)`) are name labels, not value loads. With the `==` guards, both take the
    # False (exemption) side: rules.py 503 (attribute) and 505 (keyword) now reachable.
    ab = "o.attr\n".encode()
    abr = parse_python(ab).root_node
    attr_child = next(
        n for n in _w(abr) if n.type == "identifier" and node_text(n, ab) == "attr"
    )
    if _is_value_load(attr_child) is not False:
        bad.append("_is_value_load(attr name) should be False (name label, not a load)")
    kb = "g(name=1)\n".encode()
    kbr = parse_python(kb).root_node
    kw_name = next(
        n for n in _w(kbr) if n.type == "identifier" and node_text(n, kb) == "name"
    )
    if _is_value_load(kw_name) is not False:
        bad.append("_is_value_load(keyword name) should be False (name label, not a load)")
    # The object side of an attribute (`o` in `o.attr`) IS a value load — exercises the
    # True fall-through past the attribute guard (parent is attribute but node is not the
    # attribute field).
    attr_obj = next(
        n for n in _w(abr) if n.type == "identifier" and node_text(n, ab) == "o"
    )
    if _is_value_load(attr_obj) is not True:
        bad.append("_is_value_load(attribute object) should be True")
    # The value side of a keyword argument is a value load too; here the keyword value is an
    # integer, so use a name value to exercise the keyword guard's non-name-field True path.
    kb2 = "g(p=q)\n".encode()
    kbr2 = parse_python(kb2).root_node
    kw_val = next(
        n for n in _w(kbr2) if n.type == "identifier" and node_text(n, kb2) == "q"
    )
    if _is_value_load(kw_val) is not True:
        bad.append("_is_value_load(keyword value) should be True")

    # Field-None defensive guards on body/parameters. Every body-bearing helper takes a
    # node argument and reads child_by_field_name("body") (or "parameters"); a node that
    # is not a function (here an integer literal) has neither field, so the guard returns
    # the empty result. These guards cannot be reached through check_source (a parsed
    # function_definition always has a body), so they are pinned by direct call — the same
    # internal-probe technique laws_hc.py uses for the LSP/startup internals.
    if _class_methods(integer) != []:
        bad.append("_class_methods(non-class) should be []")
    if _direct_nonlocal_names(integer, src_b) != set():
        bad.append("_direct_nonlocal_names(non-func) should be set()")
    if _local_names(integer, src_b) != set():
        bad.append("_local_names(non-func) should be set()")
    if _produced_slot_keys(integer, src_b) != set():
        bad.append("_produced_slot_keys(non-func) should be set()")
    # A link body with a subscript-string assignment (manifest['k'] = ...) drives
    # _produced_slot_keys's subscript loop (rules.py 1058) and the string-value capture.
    # check_source never extracts this helper in isolation with such a body, so it is pinned
    # by direct call on a real function node.
    psk_b = "def f():\n    m['slot_a'] = 1\n    m[0] = 2\n    return m\n".encode()
    psk_root = parse_python(psk_b).root_node
    psk_fn = next(n for n in _w(psk_root) if n.type == "function_definition")
    if _produced_slot_keys(psk_fn, psk_b) != {"slot_a"}:
        bad.append("_produced_slot_keys(subscript-string body) should be {'slot_a'}")
    if _orchestrator_call_sequence(integer, src_b) != []:
        bad.append("_orchestrator_call_sequence(non-func) should be []")
    if _self_attr_writes(integer, src_b) != []:
        bad.append("_self_attr_writes(non-func) should be []")
    # _check_global_reads over a tree with no mutable set is a no-op (empty list); a
    # function body whose only statements lack assignments/for-loops exercises the
    # body-None defensive guard via a non-function root too.
    if _check_global_reads(root, src_b, "f.py", set()) != []:
        bad.append("_check_global_reads(no mutable) should be []")
    # _call_name of a node with no function field (a non-call) -> ''.
    if _call_name(integer, src_b) != "":
        bad.append("_call_name(non-call) should be ''")

    # function_calls over a non-function node (body field absent) -> empty set. The same
    # body-None guard appears in several declgraph extractors; this pins the declgraph one.
    if function_calls(integer, src_b) != set():
        bad.append("function_calls(non-func) should be set()")

    # The arguments-None guards on the call-shaped accessors. A non-call node has no
    # "arguments" field, so each returns its empty default. Real constructor calls always
    # carry an argument_list, so these guards are unreachable through check_source.
    if _dictionary_arg(integer) is not None:
        bad.append("_dictionary_arg(non-call) should be None")
    if positional_arg_count(integer) != 0:
        bad.append("positional_arg_count(non-call) should be 0")
    if keyword_args(integer, src_b) != {}:
        bad.append("keyword_args(non-call) should be {}")

    # _parse_composed over a non-call node: no positional-string name, no arguments, no
    # requires/captures -> the empty record. Pins the args-None positional-name skip.
    record = _parse_composed(integer, src_b)
    if record["name"] is not None or record["requires"] != set() or record["captures"] is not None:
        bad.append("_parse_composed(non-call) should be an empty record")

    return bad


def run() -> int:
    failed = 0
    passed = 0
    total = 0
    for label, source, must_fire, must_not_fire in _CASES:
        total += 1
        fired = _rules(source)
        problems = []
        for rule in must_fire:
            if rule not in fired:
                problems.append(f"expected {rule}, got {sorted(set(fired))}")
        for rule in must_not_fire:
            if rule in fired:
                problems.append(f"did not expect {rule}, got {sorted(set(fired))}")
        if problems:
            failed += 1
            print(f"FAIL HC-rule [{label}]: {problems}")
        else:
            passed += 1

    total += 1
    helper_bad = _probe_internal_helpers()
    if helper_bad:
        failed += 1
        print(f"FAIL HC-rule [internal_helpers]: {helper_bad}")
    else:
        passed += 1

    print(f"HC rule laws: {passed} passed, {failed} failed, {total} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run())
