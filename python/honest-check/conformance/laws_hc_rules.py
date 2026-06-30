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
    _longest_common_run,
    _orchestrator_call_sequence,
    _produced_slot_keys,
    _self_attr_writes,
)
from honest_check.declgraph import (
    assigned_name,
    authorizing_links,
    build_vocabulary_definitions,
    constructor_calls,
    extract_bindings,
    extract_chains,
    extract_composed_types,
    extract_links,
    extract_routes,
    extract_state_machines,
    extract_vocabularies,
    feature_state_calls,
    feature_vocabulary,
    function_calls,
    function_name,
    handler_table_dispatches,
    module_dict_keys,
    function_role,
    is_provider_registered,
    keyword_args,
    link_decorator_call,
    module_assignments,
    positional_arg_count,
    resolve_aliases,
    string_value,
    string_list,
    transition_table,
    vocab_binding_pairings,
    vocab_expr_type_names,
    vocabulary_base_types,
    vocabulary_members,
    _dictionary_arg,
    _feature_state_flag,
    _parse_composed,
    _recognizer,
    _route_key,
)
from honest_parse import parse_python, parse_javascript, node_text, walk as _w
from honest_check.rules import language_for_path
from honest_check.js_rules import _class_base, _class_name, _is_class_node, _js_call_name


def _rules(source: str) -> list[str]:
    return [d["rule"] for d in check_source(source, "f.py")]


# Each case: (label, source, must_fire, must_not_fire).
# must_fire   — rule ids that MUST appear in the diagnostics for this snippet.
# must_not_fire — rule ids that MUST NOT appear (clean-path / negative assertions).
_CASES: list[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = []


def _case(label, source, must_fire=(), must_not_fire=()):
    _CASES.append((label, source, tuple(must_fire), tuple(must_not_fire)))


def _js_rules(source: str) -> list[str]:
    return [d["rule"] for d in check_source(source, "f.js")]


# JavaScript cases run through check_source with a .js path, exercising the JavaScript grammar and
# rule registry (section 5).
_JS_CASES: list[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = []


def _js_case(label, source, must_fire=(), must_not_fire=()):
    _JS_CASES.append((label, source, tuple(must_fire), tuple(must_not_fire)))


# ----------------------------------------------------------------- HC-P003 (JavaScript)

_js_case("js_p003_bare", "class Widget {}", must_fire=("HC-P003",))
_js_case("js_p003_extends_other", "class Widget extends Gadget {}", must_fire=("HC-P003",))
_js_case("js_p003_extends_error_clean", "class MyErr extends Error {}", must_not_fire=("HC-P003",))
_js_case("js_p003_anonymous_extends", "const C = class extends Y {};", must_fire=("HC-P003",))
_js_case("js_pure_function_clean", "function add(a, b) {\n    return a + b;\n}\n", must_not_fire=("HC-P003",))


# ----------------------------------------------------------------- HC-P011 (JavaScript)

_js_case("js_p011_add_event_listener", "el.addEventListener('click', h);", must_fire=("HC-P011",))
_js_case("js_p011_use_effect", "useEffect(fn);", must_fire=("HC-P011",))
_js_case("js_p011_plain_method_clean", "el.appendChild(node);", must_not_fire=("HC-P011",))


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
    must_not_fire=("HC-A002",),  # no provider -> HC-A001's job, HC-A002 stays silent
)
_case(
    "a001_provider_registered_clean",
    "from honest_type import link\n"
    "@link(authorizes=True)\n"
    "def f(x):\n    return actor\n"
    "p = AuthProvider(resolve_actor=validate)\n"
    "register_auth_provider(p)\n",
    must_not_fire=("HC-A001", "HC-A002"),
)
_case(
    "a001_no_authorizing_links_clean",
    "from honest_type import link\n@link(accepts=A)\ndef f(x):\n    return x\n",
    must_not_fire=("HC-A001",),
)
_case(
    "a002_actor_from_input",
    "from honest_type import link\n"
    "@link(authorizes=True)\n"
    "def f(x):\n    return x\n"
    "register_auth_provider(p)\n",
    must_fire=("HC-A002",),
)
_case(
    "a002_uses_boundary_actor_clean",
    "from honest_type import link\n"
    "@link(authorizes=True)\n"
    "def f(x):\n    return owns(actor, x)\n"
    "register_auth_provider(p)\n",
    must_not_fire=("HC-A002",),
)
_case(
    "a001_provider_not_inline_clean",
    "from honest_type import link\n"
    "@link(authorizes=True)\n"
    "def f(x):\n    return actor\n"
    "register_auth_provider(some_provider)\n",
    must_not_fire=("HC-A001", "HC-A002"),
)


# ----------------------------------------------------------------- HC-HF001 / HC-HF002 feature flags

_FEAT = "FEATURES = {'new_checkout': {'states': {'on', 'off'}, 'default': 'off'}}\n"

# HF001 — feature_state referencing a flag not declared in FEATURES is an error.
_case(
    "hf001_undeclared_flag",
    _FEAT + "def f(state, m):\n    return feature_state(state, 'ghost')\n",
    must_fire=("HC-HF001",),
)
_case(
    "hf001_declared_flag_clean",
    _FEAT + "def f(state, m):\n    return feature_state(state, 'new_checkout')\n",
    must_not_fire=("HC-HF001",),
)
_case(
    "hf001_no_features_skip",
    "def f(state, m):\n    return feature_state(state, 'ghost')\n",
    must_not_fire=("HC-HF001",),  # no in-module FEATURES to verify against
)
_case(
    "hf001_nonstring_flag_clean",
    _FEAT + "def f(state, flag):\n    return feature_state(state, flag)\n",
    must_not_fire=("HC-HF001",),  # flag is a variable, not a literal — nothing to check
)
_case(
    "hf001_features_not_dict_skip",
    "FEATURES = build()\ndef f(state, m):\n    return feature_state(state, 'ghost')\n",
    must_not_fire=("HC-HF001",),  # FEATURES is not a dict literal — vocabulary unreadable
)

# HF002 — a handler table keyed on a flag must cover every declared state of that flag.
_HANDLERS_PARTIAL = "HANDLERS = {'on': h1}\n"
_HANDLERS_FULL = "HANDLERS = {'on': h1, 'off': h2}\n"
_case(
    "hf002_missing_handler",
    _FEAT + _HANDLERS_PARTIAL + "def f(state, m):\n    return HANDLERS[feature_state(state, 'new_checkout')](m)\n",
    must_fire=("HC-HF002",),
)
_case(
    "hf002_complete_handler_clean",
    _FEAT + _HANDLERS_FULL + "def f(state, m):\n    return HANDLERS[feature_state(state, 'new_checkout')](m)\n",
    must_not_fire=("HC-HF002",),
)
_case(
    "hf002_table_not_dict_skip",
    _FEAT + "def f(state, m):\n    return get_handlers()[feature_state(state, 'new_checkout')](m)\n",
    must_not_fire=("HC-HF002",),  # the table is not a module dict literal — unreadable
)
_case(
    "hf002_undeclared_flag_skip",
    _FEAT + _HANDLERS_PARTIAL + "def f(state, m):\n    return HANDLERS[feature_state(state, 'ghost')](m)\n",
    must_fire=("HC-HF001",),
    must_not_fire=("HC-HF002",),  # undeclared flag is HF001's job
)
_case(
    "hf002_states_as_list",
    "FEATURES = {'new_checkout': {'states': ['on', 'off'], 'default': 'off'}}\n"
    + _HANDLERS_PARTIAL
    + "def f(state, m):\n    return HANDLERS[feature_state(state, 'new_checkout')](m)\n",
    must_fire=("HC-HF002",),  # states declared as a list still enumerate
)
_case(
    "hf001_too_few_args_clean",
    _FEAT + "def f(state):\n    return feature_state(state)\n",
    must_not_fire=("HC-HF001",),  # one argument — no flag literal to check
)
# Malformed FEATURES shapes the vocabulary extractor must read without crashing or mis-firing:
# a top-level spread, a non-dict entry, a spec-level spread, a spec whose states are a name, a
# spec with no states pair, and a non-states pair before the states pair.
_case(
    "hf_vocabulary_odd_shapes",
    "FEATURES = {**base, "
    "'nc': {'default': 'off', 'states': {'on', 'off'}}, "
    "'bad': 'x', "
    "'nostates': {'default': 'a'}, "
    "'namedstates': {'states': REF, 'default': 'a'}, "
    "'sp': {**inner, 'states': {'on', 'off'}, 'default': 'on'}}\n"
    "def f(state, m):\n    return feature_state(state, 'nc')\n",
    must_not_fire=("HC-HF001", "HC-HF002"),
)
_case(
    "hf002_table_not_dict_module",
    _FEAT + "HANDLERS = make()\ndef f(state, m):\n    return HANDLERS[feature_state(state, 'new_checkout')](m)\n",
    must_not_fire=("HC-HF002",),  # HANDLERS is bound to a call, not a dict literal — unreadable
)
_case(
    "hf002_subscript_variants_clean",
    _FEAT
    + _HANDLERS_FULL
    + "def f(state, m):\n"
    "    x = HANDLERS['on']\n"  # index is not a feature_state call
    "    y = get()[feature_state(state, 'new_checkout')]\n"  # table is not an identifier
    "    return HANDLERS[feature_state(state, 'new_checkout')](m)\n",
    must_not_fire=("HC-HF002",),
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
# A provider registered amid noise (a non-call module assignment, an unrelated call) is detected:
# the authorizing link uses the boundary actor, so neither HC-A001 nor HC-A002 fires.
_case(
    "declgraph_auth_provider_registered_clean",
    "from honest_type import link\n"
    "@link(authorizes=True)\n"
    "def f(x):\n    return owns(actor, x)\n"
    "count = 5\n"
    "noise = compute()\n"
    "register_auth_provider(p)\n",
    must_not_fire=("HC-A001", "HC-A002"),
)


# ----------------------------------------------------------------- HC-SYN

_case(
    "syntax_error",
    "def (:\n    pass\n",
    must_fire=("HC-SYN",),
)


# ----------------------------------------------------------------- direct-call probes

def _probe_javascript() -> list[str]:
    """Pin the JavaScript path of check_source (section 5): language dispatch, the HC-P003 messages and
    severities, suppression via `// honest:`, and the class-shape helpers. The JS cases assert which rule
    fires; this pins the exact text, the info downgrade, and the helper return values."""
    bad: list[str] = []

    def js(src):
        return [d for d in check_source(src, "f.js") if d["rule"] == "HC-P003"]

    bare = js("class Widget {}")
    if not bare or bare[0]["message"] != "Class 'Widget' has no declared base. Honest Code permits a JavaScript class only as a subclass of Error. Use a plain object for data or a pure function.":
        bad.append(f"JS HC-P003 bare message drifted: {bare}")
    if not bare or bare[0]["severity"] != "error":
        bad.append(f"JS HC-P003 should be an error: {bare}")
    inh = js("class Widget extends Gadget {}")
    if not inh or inh[0]["message"] != "Class 'Widget' inherits from 'Gadget'. Use composition over inheritance.":
        bad.append(f"JS HC-P003 inherits message drifted: {inh}")
    anon = js("const C = class extends Y {};")
    if not anon or anon[0]["message"] != "Class '<anonymous>' inherits from 'Y'. Use composition over inheritance.":
        bad.append(f"JS HC-P003 anonymous message drifted: {anon}")
    sup = js("class Widget {} // honest: ignore HC-P003")
    if not sup or sup[0]["severity"] != "info" or sup[0]["message"] != "HC-P003 suppressed by directive.":
        bad.append(f"JS // honest: suppression should downgrade to info: {sup}")

    for path, language in [("a.js", "javascript"), ("a.mjs", "javascript"), ("a.cjs", "javascript"), ("a.py", "python"), ("noext", "python")]:
        if language_for_path(path) != language:
            bad.append(f"language_for_path({path!r}) != {language!r}: {language_for_path(path)}")

    # The class-expression node is a class; the bare `class` keyword token (no body) is not.
    root = parse_javascript(b"const C = class extends Y {};").root_node
    class_nodes = [n for n in _w(root) if _is_class_node(n)]
    if len(class_nodes) != 1:
        bad.append(f"_is_class_node should match exactly the class expression, not the keyword token: {len(class_nodes)}")
    if _class_name(class_nodes[0], b"const C = class extends Y {};") != "<anonymous>":
        bad.append("_class_name of an anonymous class should be '<anonymous>'")
    bare_root = parse_javascript(b"class Widget {}").root_node
    bare_class = next(n for n in _w(bare_root) if _is_class_node(n))
    if _class_base(bare_class, b"class Widget {}") is not None:
        bad.append("_class_base of a class with no heritage should be None")

    # HC-P011: a lifecycle hook (plain call and member call) fires as an error; a plain method does not.
    hook = [d for d in check_source("el.addEventListener('click', h);", "f.js") if d["rule"] == "HC-P011"]
    if not hook or hook[0]["message"] != "Lifecycle hook 'addEventListener'. Use HTMX attributes or server-rendered HTML.":
        bad.append(f"JS HC-P011 message drifted: {hook}")
    if not hook or hook[0]["severity"] != "error":
        bad.append(f"JS HC-P011 should be an error: {hook}")
    # _js_call_name: a plain call's identifier callee, a member call's property, and "" off a non-call.
    call_root = parse_javascript(b"useEffect(fn);").root_node
    plain_call = next(n for n in _w(call_root) if n.type == "call_expression")
    if _js_call_name(plain_call, b"useEffect(fn);") != "useEffect":
        bad.append("_js_call_name of a plain call should be the identifier")
    member_root = parse_javascript(b"el.addEventListener(h);").root_node
    member_call = next(n for n in _w(member_root) if n.type == "call_expression")
    if _js_call_name(member_call, b"el.addEventListener(h);") != "addEventListener":
        bad.append("_js_call_name of a member call should be the property")
    if _js_call_name(call_root, b"useEffect(fn);") != "":
        bad.append("_js_call_name of a non-call node should be ''")
    # Every lifecycle-hook member fires (section 9.6 vocabulary-member coverage): a hardcoded list,
    # independent of the rule's frozenset, so emptying any member is caught.
    for hook in (
        "useEffect", "useLayoutEffect", "componentDidMount", "componentDidUpdate",
        "componentWillUnmount", "ngOnInit", "ngOnDestroy", "addEventListener", "removeEventListener",
    ):
        if "HC-P011" not in [d["rule"] for d in check_source(f"obj.{hook}(a);", "f.js")]:
            bad.append(f"HC-P011 should fire for lifecycle hook {hook!r}")
    return bad


def _probe_feature_extractors() -> list[str]:
    """Pin the exact output of the feature-flag declgraph extractors (honest-features sections 2, 7).

    The HF rule cases drive these through check_source, but assert only the diagnostics. Pinning each
    extractor's return value directly catches mutations to the guards and the excluded-argument tuple
    that leave the diagnostics unchanged. Pure: source in, data out.
    """
    bad: list[str] = []

    def vocab(src):
        b = src.encode()
        return feature_vocabulary(parse_python(b).root_node, b)

    def flags(src):
        b = src.encode()
        return [f for f, _ in feature_state_calls(parse_python(b).root_node, b)]

    def dispatches(src):
        b = src.encode()
        return [(t, f) for t, f, _ in handler_table_dispatches(parse_python(b).root_node, b)]

    def dict_keys(name, src):
        b = src.encode()
        return module_dict_keys(name, parse_python(b).root_node, b)

    # feature_vocabulary — set and list states; only FEATURES is read.
    if vocab("FEATURES = {'nc': {'states': {'on', 'off'}, 'default': 'off'}, 'pr': {'states': ['a', 'b'], 'default': 'a'}}\n") != {"nc": frozenset({"on", "off"}), "pr": frozenset({"a", "b"})}:
        bad.append("feature_vocabulary should read set and list states")
    if vocab("OTHER = {'x': {'states': {'a', 'b'}, 'default': 'a'}}\n") != {}:
        bad.append("feature_vocabulary should ignore a non-FEATURES assignment")
    if vocab("FEATURES = make()\n") != {}:
        bad.append("feature_vocabulary of a non-dict FEATURES should be empty")
    if vocab("FEATURES: dict\n") != {}:
        bad.append("feature_vocabulary of an annotation-only FEATURES should be empty")
    if vocab("FEATURES = {1: {'states': {'a', 'b'}, 'default': 'a'}, 'nc': {'states': {'on', 'off'}, 'default': 'off'}}\n") != {"nc": frozenset({"on", "off"})}:
        bad.append("feature_vocabulary should skip a non-string flag key")
    if vocab("FEATURES = {**base, 'bad': 'x', 'nc': {'states': {'on', 'off'}, 'default': 'off'}}\n") != {"nc": frozenset({"on", "off"})}:
        bad.append("feature_vocabulary should skip a non-dict spec and a spread")
    if vocab("FEATURES = {'ns': {'default': 'a'}, 'nm': {'states': REF, 'default': 'a'}}\n") != {"ns": frozenset(), "nm": frozenset()}:
        bad.append("feature_vocabulary states should be empty when absent or not a set/list")
    # states declared as a tuple are not a Set/list recognizer, so they are ignored (not read as members).
    if vocab("FEATURES = {'tp': {'states': ('on', 'off'), 'default': 'on'}}\n") != {"tp": frozenset()}:
        bad.append("feature_vocabulary should ignore tuple-valued states")
    if vocab("FEATURES = {'al': {'aliases': {'x', 'y'}, 'states': {'on', 'off'}, 'default': 'on'}}\n") != {"al": frozenset({"on", "off"})}:
        bad.append("feature_vocabulary must read states, not another set-valued pair")
    if vocab("FEATURES = {'sp': {**inner, 'states': {'on', 'off'}, 'default': 'on'}}\n") != {"sp": frozenset({"on", "off"})}:
        bad.append("feature_vocabulary should skip a spec-level spread")

    # feature_state_calls — literal flag extracted; non-call, too-few args, non-literal flag, a comment
    # between args, and a star-splat before the flag yield nothing or the right flag.
    if flags("def f(s):\n    feature_state(s, 'a')\n    feature_state(s, 'b')\n") != ["a", "b"]:
        bad.append("feature_state_calls should list each string flag")
    if flags("def f(s):\n    other(s, 'a')\n") != []:
        bad.append("feature_state_calls should ignore a non-feature_state call")
    if flags("def f(s):\n    feature_state(s)\n") != []:
        bad.append("feature_state_calls should ignore a one-argument call")
    if flags("def f(s, g):\n    feature_state(s, g)\n") != []:
        bad.append("feature_state_calls should ignore a non-literal flag")
    if flags("def f(s):\n    feature_state(s,  # note\n        'a')\n") != ["a"]:
        bad.append("feature_state_calls should skip a comment between arguments")
    if flags("def f(s):\n    feature_state(*s, 'a')\n") != []:
        bad.append("feature_state_calls should not count a flag after a star-splat as the second positional")

    # handler_table_dispatches — TABLE[feature_state(...)] captured; literal index and non-identifier
    # table yield nothing.
    if dispatches("def f(s, m):\n    return T[feature_state(s, 'a')](m)\n") != [("T", "a")]:
        bad.append("handler_table_dispatches should capture a flag dispatch")
    if dispatches("def f(s, m):\n    return T['lit'](m)\n") != []:
        bad.append("handler_table_dispatches should ignore a literal index")
    if dispatches("def f(s, m):\n    return get()[feature_state(s, 'a')](m)\n") != []:
        bad.append("handler_table_dispatches should ignore a non-identifier table")

    # module_dict_keys — keys of a dict literal; a non-dict binding and a missing name yield None.
    if dict_keys("H", "H = {'on': a, 'off': b}\n") != frozenset({"on", "off"}):
        bad.append("module_dict_keys should read a dict literal's keys")
    if dict_keys("H", "H = make()\n") is not None:
        bad.append("module_dict_keys of a non-dict binding should be None")
    if dict_keys("H", "X = {'on': a}\n") is not None:
        bad.append("module_dict_keys of a missing name should be None")

    return bad


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

    # _feature_state_flag(None) -> None. handler_table_dispatches passes the subscript's index node,
    # which a parsed subscript always carries, so the None guard is unreachable through check_source.
    if _feature_state_flag(None, src_b) is not None:
        bad.append("_feature_state_flag(None) should be None")

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

    # _longest_common_run (HC-OR003): longest *contiguous* common sublist. Pins the empty guard, the
    # best/return-0 bases, the DP row sizing, and the loop ranges.
    if _longest_common_run([], ["a"]) != 0 or _longest_common_run(["a"], []) != 0:
        bad.append("_longest_common_run with an empty sequence should be 0")
    if _longest_common_run(["a"], ["b"]) != 0:
        bad.append("_longest_common_run with no common element should be 0")
    if _longest_common_run(["a"], ["a"]) != 1:
        bad.append("_longest_common_run of a single shared element should be 1")
    if _longest_common_run(["a", "b", "c", "d"], ["x", "a", "b", "c"]) != 3:
        bad.append("_longest_common_run should find the length-3 contiguous run")
    if _longest_common_run(["a", "b", "c"], ["a", "x", "c"]) != 1:
        bad.append("_longest_common_run must be contiguous: a broken run counts 1")
    if _longest_common_run(["a", "b"], ["b", "a"]) != 1:
        bad.append("_longest_common_run of a reordered pair is at most 1")
    if _longest_common_run(["a", "b"], ["b"]) != 1:
        bad.append("_longest_common_run must seed each row from zero (a match after a miss counts 1)")

    return bad


def _pa(src: str):
    """Parse to (root, source_bytes)."""
    b = src.encode()
    return parse_python(b).root_node, b


# A diagnostic that could be reported twice but is deduplicated to one: pins each rule's `seen` set
# (a missing seen.add or `key in seen` skip would emit the duplicate). Each source triggers the same
# finding twice (a name read twice, or two identical link pairings).
_DEDUP_CASES = [
    ("HC-P004", "d = {}\nd[0] = 1\ndef f():\n    return d[0] + d[1]\n"),
    ("HC004", "from honest_type import vocabulary, binding, link\nV = vocabulary({'a': {'x'}, 'b': {'y'}})\nB = binding({'a': 's1'})\n@link(accepts=V, binds=B)\ndef f(x):\n    return x\n@link(accepts=V, binds=B)\ndef g(x):\n    return x\n"),
    ("HC005", "from honest_type import vocabulary, binding, link\nV = vocabulary({'a': {'x'}})\nB = binding({'a': 's1', 'ghost': 's2'})\n@link(accepts=V, binds=B)\ndef f(x):\n    return x\n@link(accepts=V, binds=B)\ndef g(x):\n    return x\n"),
    ("HC-P013", "from honest_type import vocabulary, binding, link, predicate\nV = vocabulary({'db': predicate(p)})\nB = binding({'db': 'db_id'})\n@link(accepts=V, binds=B)\ndef f(x):\n    return x\n@link(accepts=V, binds=B)\ndef g(x):\n    return x\n"),
    ("HC-P014", "from honest_type import vocabulary, binding, link\nV = vocabulary({'a': {'x'}, 'b': {'x'}, 'c': {'q'}})\nB = binding({'a': 'slot1', 'b': 'slot2', 'ghost': 'slotg'})\n@link(accepts=V, binds=B)\ndef f(x):\n    return x\n@link(accepts=V, binds=B)\ndef g(x):\n    return x\n"),
]


def _probe_dedup() -> list[str]:
    """Each duplicate-prone finding is reported exactly once (the rule's `seen` dedup is load-bearing)."""
    bad = []
    for rule, source in _DEDUP_CASES:
        n = sum(1 for d in check_source(source, "f.py") if d["rule"] == rule)
        if n != 1:
            bad.append(f"{rule} should be deduplicated to one diagnostic, got {n}")
    return bad


def _probe_declgraph_extractors() -> list[str]:
    """Pin the declaration-graph extractors directly with exact-output assertions (sections 3.3-3.4).

    The rule cases above drive these extractors indirectly through check_source, but never assert the
    extracted structures themselves, so a dropped append, a flipped guard, or a swapped dict key can
    leave the rule verdict unchanged. Here each extractor is fed a crafted source and its full output
    is pinned, with discriminating malformed inputs for the defensive branches.
    """
    bad: list[str] = []

    # resolve_aliases: from-imports (dotted + aliased), import-as and bare import for the module forms,
    # and the negatives (a non-honest aliased import, a non-honest from-import, a plain import).
    root, b = _pa(
        "from honest_type import vocabulary, binding, composed, chain, classify, state_machine, predicate\n"
        "from honest_type import link as lk\n"
        "import honest_type as ht\n"
        "import honest_type\n"
        "import json as j\n"
        "from other_mod import vocabulary as v\n"
        "import os\n"
    )
    names, modules = resolve_aliases(root, b)
    if names != {
        "vocabulary": "vocabulary", "binding": "binding", "composed": "composed", "chain": "chain",
        "classify": "classify", "state_machine": "state_machine", "predicate": "predicate", "lk": "link",
    }:
        bad.append(f"resolve_aliases names wrong: {names}")
    if modules != {"ht", "honest_type"}:
        bad.append(f"resolve_aliases modules wrong: {modules}")

    aliases = (names, modules)

    # constructor_calls: the bare-identifier form and the module-attribute form (ht.chain), and the
    # negatives (a chain via an unknown module, a non-honest identifier call).
    root, b = _pa(
        "from honest_type import chain\n"
        "import honest_type as ht\n"
        "c1 = chain(a)\nc2 = ht.chain(a)\nc3 = zz.chain(a)\nc4 = other(a)\n"
    )
    al = resolve_aliases(root, b)
    chains = constructor_calls(root, b, al, "chain")
    if len(chains) != 2:
        bad.append(f"constructor_calls(chain) should find the identifier and module-attribute forms: {len(chains)}")

    # assigned_name: an assignment target, and the no-assignment / non-identifier-target negatives.
    root, b = _pa(
        "from honest_type import vocabulary\n"
        "V = vocabulary({'a': {'x'}})\nvocabulary({'b': {'y'}})\no.attr = vocabulary({'c': {'z'}})\n"
    )
    al = resolve_aliases(root, b)
    calls = constructor_calls(root, b, al, "vocabulary")
    assigned = [assigned_name(c, b) for c in calls]
    if assigned != ["V", None, None]:
        bad.append(f"assigned_name should read an identifier target only: {assigned}")

    # vocabulary_base_types + _recognizer: set / predicate / ref recognizers, an empty-string key kept,
    # and a non-string (integer) key skipped.
    root, b = _pa(
        "from honest_type import vocabulary\n"
        "V = vocabulary({'s': {'x', 'y'}, 'r': other, 'p': pred(z), 5: {'q'}})\n"
    )
    al = resolve_aliases(root, b)
    call = constructor_calls(root, b, al, "vocabulary")[0]
    base = vocabulary_base_types(call, b)
    if set(base) != {"s", "r", "p"}:
        bad.append(f"vocabulary_base_types keys wrong (int key skipped): {sorted(base)}")
    if base["s"] != ("set", frozenset({"x", "y"})) or base["r"] != ("ref", "other") or base["p"][0] != "predicate":
        bad.append(f"_recognizer tagging wrong: {base}")
    if vocabulary_members(call, b) != {"x", "y"}:
        bad.append(f"vocabulary_members should union only Set members: {vocabulary_members(call, b)}")
    # A non-vocabulary (no dict) call yields no base types.
    root2, b2 = _pa("from honest_type import vocabulary\nV = vocabulary()\n")
    al2 = resolve_aliases(root2, b2)
    if vocabulary_base_types(constructor_calls(root2, b2, al2, "vocabulary")[0], b2) != {}:
        bad.append("vocabulary_base_types of a no-dict call should be {}")

    # extract_vocabularies: base + composed records + composed_names, keyed by var name.
    root, b = _pa(
        "from honest_type import vocabulary, composed\n"
        "V = vocabulary({'a': {'x'}}, composed_types=[composed('combo', requires={'a': 1}, captures='b')])\n"
        "vocabulary({'unnamed': {'q'}})\n"
    )
    al = resolve_aliases(root, b)
    vocabs = extract_vocabularies(root, b, al)
    if set(vocabs) != {"V"} or vocabs["V"]["composed_names"] != {"combo"}:
        bad.append(f"extract_vocabularies should key by name, skipping the unnamed call: {set(vocabs)}")
    if vocabs["V"]["base"] != {"a": ("set", frozenset({"x"}))}:
        bad.append(f"extract_vocabularies base wrong: {vocabs['V']['base']}")
    composed = vocabs["V"]["composed"]
    if len(composed) != 1 or composed[0]["name"] != "combo" or composed[0]["requires"] != {"a"} or composed[0]["captures"] != "b":
        bad.append(f"extract_composed_types record wrong: {composed}")

    # _parse_composed: name via keyword (no positional string), requires keys, and a maybe()-wrapped capture.
    root, b = _pa(
        "from honest_type import composed\n"
        "c = composed(name='kw', requires={'t': 1}, captures=maybe('integer'))\n"
    )
    al = resolve_aliases(root, b)
    comp_call = constructor_calls(root, b, al, "composed")[0]
    rec = _parse_composed(comp_call, b)
    if rec["name"] != "kw" or rec["requires"] != {"t"} or rec["captures"] != "integer":
        bad.append(f"_parse_composed kw/maybe wrong: {rec}")
    # extract_composed_types skips a non-composed element and a non-call element.
    root, b = _pa(
        "from honest_type import vocabulary, composed\n"
        "V = vocabulary({'a': {'x'}}, composed_types=[composed('ok'), other('no'), 5])\n"
    )
    al = resolve_aliases(root, b)
    only = extract_composed_types(constructor_calls(root, b, al, "vocabulary")[0], b, al)
    if [r["name"] for r in only] != ["ok"]:
        bad.append(f"extract_composed_types should keep only composed(...) calls: {[r['name'] for r in only]}")

    # extract_bindings: table of type->slot, name-None skip, and non-string key/value skip.
    root, b = _pa(
        "from honest_type import binding\n"
        "B = binding({'t': 'slot', 5: 'x', 'u': 9})\n"
        "binding({'t': 'unnamed'})\n"
    )
    al = resolve_aliases(root, b)
    bindings = extract_bindings(root, b, al)
    if set(bindings) != {"B"} or bindings["B"]["table"] != {"t": "slot"}:
        bad.append(f"extract_bindings table wrong (non-string and unnamed skipped): {bindings}")

    # build_vocabulary_definitions + vocab_expr_type_names: a defined vocab, a merge (a | b),
    # an inline vocabulary call, a parenthesized merge, and a non-identifier-left skip.
    root, b = _pa(
        "from honest_type import vocabulary\n"
        "A = vocabulary({'a': {'x'}})\n"
        "Bv = vocabulary({'b': {'y'}})\n"
        "M = A | Bv\n"
        "P = (A | vocabulary({'c': {'z'}}))\n"
        "o.attr = vocabulary({'d': {'w'}})\n"
    )
    al = resolve_aliases(root, b)
    defs = build_vocabulary_definitions(root, b, al)
    if defs.get("A") != {"a"} or defs.get("M") != {"a", "b"} or defs.get("P") != {"a", "c"}:
        bad.append(f"build_vocabulary_definitions merge/paren wrong: {defs}")
    if "o.attr" in defs or any(not isinstance(k, str) or "." in k for k in defs):
        bad.append(f"build_vocabulary_definitions should skip non-identifier targets: {sorted(defs)}")

    # link_decorator_call + extract_links: accepts/emits resolved, boundary flag true vs default false.
    root, b = _pa(
        "from honest_type import vocabulary, link\n"
        "A = vocabulary({'a': {'x'}})\n"
        "Bv = vocabulary({'b': {'y'}})\n"
        "@link(accepts=A, emits=Bv, boundary=True)\n"
        "def f(d):\n    return d\n"
        "@link(accepts=A, emits=A)\n"
        "def g(d):\n    return d\n"
        "def plain():\n    return 1\n"
    )
    al = resolve_aliases(root, b)
    defs = build_vocabulary_definitions(root, b, al)
    links = extract_links(root, b, al, defs)
    if set(links) != {"f", "g"}:
        bad.append(f"extract_links should find only @link functions: {sorted(links)}")
    if links["f"]["accepts"] != {"a"} or links["f"]["emits"] != {"b"} or links["f"]["boundary"] is not True:
        bad.append(f"extract_links f wrong: {links['f']}")
    if links["g"]["boundary"] is not False:
        bad.append(f"extract_links g boundary should default False: {links['g']}")
    if "location" not in links["f"] or links["f"]["location"][0] <= 0:
        bad.append(f"extract_links should carry a 1-based location: {links['f']}")

    # link_decorator_call negatives: a plain (undecorated) function, and a function decorated by a
    # non-link call, both yield None.
    root2, b2 = _pa("def plain():\n    return 1\n@other()\ndef h():\n    return 2\n")
    al2 = resolve_aliases(root2, b2)
    funcs = {function_name(n, b2): n for n in _w(root2) if n.type == "function_definition"}
    if link_decorator_call(funcs["plain"], b2, al2) is not None:
        bad.append("link_decorator_call(plain) should be None")
    if link_decorator_call(funcs["h"], b2, al2) is not None:
        bad.append("link_decorator_call(non-link decorator) should be None")

    # function_role: every role decorator is recognised (bare and call forms), plus the non-role and
    # undecorated negatives. Each of the five _ROLE_DECORATORS members must be honoured.
    for role in ("link", "recognizer", "boundary", "helper", "orchestrator"):
        root, b = _pa(f"@{role}\ndef f():\n    return 1\n")
        fn = next(n for n in _w(root) if n.type == "function_definition")
        if function_role(fn, b) != role:
            bad.append(f"function_role should recognise the @{role} decorator: {function_role(fn, b)}")
    root, b = _pa(
        "@orchestrator()\ndef bb():\n    return 1\n"
        "@staticmethod\ndef c():\n    return 1\n"
        "def d():\n    return 1\n"
    )
    funcs = {function_name(n, b): n for n in _w(root) if n.type == "function_definition"}
    if function_role(funcs["bb"], b) != "orchestrator":
        bad.append("function_role should read the call form of a role decorator")
    if function_role(funcs["c"], b) is not None or function_role(funcs["d"], b) is not None:
        bad.append("function_role of a non-role / undecorated function should be None")
    if function_name(funcs["bb"], b) != "bb":
        bad.append("function_name wrong")

    # function_calls: bare-identifier callees inside the body only.
    root, b = _pa("def f():\n    g()\n    obj.method()\n    h(1)\n    return g\n")
    fn = next(n for n in _w(root) if n.type == "function_definition")
    if function_calls(fn, b) != {"g", "h"}:
        bad.append(f"function_calls should collect bare-identifier callees: {function_calls(fn, b)}")

    # vocab_binding_pairings: the @link(accepts=, binds=) form and the classify(_, vocab, bind) positional form.
    root, b = _pa(
        "from honest_type import link, classify\n"
        "@link(accepts=Voc, binds=Bind)\n"
        "def f(d):\n    return d\n"
        "classify(thing, Voc2, Bind2)\n"
    )
    al = resolve_aliases(root, b)
    pairs = vocab_binding_pairings(root, b, al)
    if sorted(pairs) != [("Voc", "Bind"), ("Voc2", "Bind2")]:
        bad.append(f"vocab_binding_pairings wrong: {pairs}")

    # authorizing_links: a function decorated @link(authorizes=True), and the authorizes!=True negative.
    root, b = _pa(
        "from honest_type import link\n"
        "@link(authorizes=True)\n"
        "def guard(d):\n    return d\n"
        "@link(authorizes=False)\n"
        "def open_(d):\n    return d\n"
    )
    al = resolve_aliases(root, b)
    auth = [name for name, _node in authorizing_links(root, b, al)]
    if auth != ["guard"]:
        bad.append(f"authorizing_links should find only authorizes=True: {auth}")

    # is_provider_registered: true iff a register_auth_provider(...) call is present.
    root, b = _pa("register_auth_provider(p)\n")
    if is_provider_registered(root, b) is not True:
        bad.append("is_provider_registered should be True when a provider is registered")
    root, b = _pa("x = 1\n")
    if is_provider_registered(root, b) is not False:
        bad.append("is_provider_registered should be False with no registration")

    # positional_arg_count: positionals counted, keyword args AND comments excluded.
    root, b = _pa("f(a, b, kw=1)\n")
    calln = next(n for n in _w(root) if n.type == "call")
    if positional_arg_count(calln) != 2:
        bad.append(f"positional_arg_count should exclude keyword args: {positional_arg_count(calln)}")
    root, b = _pa("f(\n    a,\n    # a comment in the args\n    b,\n    kw=1,\n)\n")
    calln = next(n for n in _w(root) if n.type == "call")
    if positional_arg_count(calln) != 2:
        bad.append(f"positional_arg_count should exclude comments and keywords: {positional_arg_count(calln)}")
    # keyword_args: only keyword_argument children become entries; positional args are not read as names.
    kw_map = keyword_args(calln, b)
    if list(kw_map) != ["kw"] or node_text(kw_map["kw"], b) != "1":
        bad.append(f"keyword_args should map only keyword arguments to their value nodes: {list(kw_map)}")

    # extract_chains: identifier links collected; a non-identifier argument is skipped.
    root, b = _pa("from honest_type import chain\nc = chain(first, second, helper())\n")
    al = resolve_aliases(root, b)
    chains = extract_chains(root, b, al)
    if len(chains) != 1 or chains[0]["name"] != "c" or chains[0]["links"] != ["first", "second"]:
        bad.append(f"extract_chains wrong: {chains}")

    # extract_routes + _route_key: a valid two-string-tuple key paired with an identifier chain, with a
    # non-tuple key, a one-string tuple, and a non-identifier value all skipped; and a non-ROUTES dict.
    root, b = _pa(
        "ROUTES = {('GET', '/a'): handler, 'x': skip1, ('POST',): skip2, ('PUT', '/b'): 'notid'}\n"
        "OTHER = {('GET', '/c'): handler}\n"
    )
    routes = extract_routes(root, b)
    if routes != [{"method": "GET", "path": "/a", "chain": "handler"}]:
        bad.append(f"extract_routes wrong: {routes}")
    root, b = _pa("ROUTES = {('GET', '/a'): h}\n")
    key_pair = next(n for n in _w(root) if n.type == "tuple")
    if _route_key(key_pair, b) != ("GET", "/a"):
        bad.append(f"_route_key wrong: {_route_key(key_pair, b)}")

    # extract_state_machines: states/events members, initial, terminal set, transitions table.
    root, b = _pa(
        "from honest_type import state_machine, vocabulary\n"
        "m = state_machine(states=vocabulary({'s': {'open', 'closed'}}), events=vocabulary({'e': {'shut'}}),"
        " initial='open', terminal=['closed'], transitions={('open', 'shut'): 'closed'})\n"
    )
    al = resolve_aliases(root, b)
    machines = extract_state_machines(root, b, al)
    if len(machines) != 1:
        bad.append(f"extract_state_machines should find one machine: {len(machines)}")
    else:
        m = machines[0]
        if (m["name"], m["states"], m["events"], m["initial"], m["terminal"], m["transitions"]) != (
            "m", {"open", "closed"}, {"shut"}, "open", {"closed"}, [("open", "shut", "closed")]
        ):
            bad.append(f"extract_state_machines parts wrong: {m}")
    # string_list accepts both a list and a tuple literal, keeping only string elements.
    root, b = _pa("x = ['a', 'b', 5]\n")
    lst = next(n for n in _w(root) if n.type == "list")
    if string_list(lst, b) != ["a", "b"]:
        bad.append(f"string_list of a list should keep only string elements: {string_list(lst, b)}")
    root, b = _pa("x = ('a', 'b')\n")
    tup = next(n for n in _w(root) if n.type == "tuple")
    if string_list(tup, b) != ["a", "b"]:
        bad.append(f"string_list of a tuple should keep only string elements: {string_list(tup, b)}")
    root, b = _pa("x = {('s', 'e'): 'n', ('only',): 'skip', 5: 'skip2'}\n")
    dct = next(n for n in _w(root) if n.type == "dictionary")
    if transition_table(dct, b) != [("s", "e", "n")]:
        bad.append(f"transition_table should keep only two-string-tuple keys: {transition_table(dct, b)}")

    # module_assignments: top-level assignments only (not one nested in a function body).
    root, b = _pa("A = 1\ndef f():\n    B = 2\n    return B\nC = 3\n")
    ma_targets = [node_text(a.child_by_field_name("left"), b) for a in module_assignments(root)]
    if ma_targets != ["A", "C"]:
        bad.append(f"module_assignments should be top-level only: {ma_targets}")

    # vocabulary_base_types: a ** spread in the base-types dict is not a pair and is skipped (the
    # pair-type guard; without it a splat has no key field and the extractor would crash).
    root, b = _pa("from honest_type import vocabulary\nV = vocabulary({**base, 'a': {'x'}})\n")
    al = resolve_aliases(root, b)
    if vocabulary_base_types(constructor_calls(root, b, al, "vocabulary")[0], b) != {"a": ("set", frozenset({"x"}))}:
        bad.append("vocabulary_base_types should skip a ** spread (non-pair) in the dict")

    # transition_table arity: a two-string tuple is kept; a one-element, a three-element, and tuples
    # with a non-string element in either position are all dropped (pins len == 2 and parts[0]/parts[1]).
    for literal, expected in (
        ("{('s', 'e'): 'n'}", [("s", "e", "n")]),
        ("{('only',): 'n'}", []),
        ("{('a', 'b', 'c'): 'n'}", []),
        ("{(5, 'e'): 'n'}", []),
        ("{('s', 5): 'n'}", []),
    ):
        root, b = _pa(f"x = {literal}\n")
        dct = next(n for n in _w(root) if n.type == "dictionary")
        if transition_table(dct, b) != expected:
            bad.append(f"transition_table({literal}) should be {expected}: {transition_table(dct, b)}")

    # classify positional boundaries (vocab = positional[1] needs >= 2; binding = positional[2] needs >= 3):
    # full positional, vocab-positional + keyword bind, and binding-positional + keyword vocab all pair;
    # and a keyword vocab that does NOT collapse the positional vocab assignment (the AND, not OR).
    for src, expected in (
        ("classify(t, V, B)\n", [("V", "B")]),               # >= 2 and >= 3 both reached
        ("classify(t, V, bind=B)\n", [("V", "B")]),          # vocab positional[1] (>= 2), binding keyword
        ("classify(t, x, B, vocab=V)\n", [("V", "B")]),      # keyword vocab kept (AND): positional[1] not used for vocab
        ("classify(t, bind=B)\n", []),                       # only one positional: vocab stays None, no pair
        ("classify(t, V, vocab=Vk)\n", []),                  # binding stays None (len 2 < 3), no pair
    ):
        root, b = _pa("from honest_type import classify\n" + src)
        al = resolve_aliases(root, b)
        if sorted(vocab_binding_pairings(root, b, al)) != expected:
            bad.append(f"vocab_binding_pairings({src.strip()}) should be {expected}: {vocab_binding_pairings(root, b, al)}")

    # function_role reads the last dotted segment of a decorator call name (mod.boundary() -> boundary).
    root, b = _pa("@mod.boundary()\ndef x():\n    return 1\n")
    fr = next(n for n in _w(root) if n.type == "function_definition")
    if function_role(fr, b) != "boundary":
        bad.append(f"function_role should read the last dotted segment of a decorator: {function_role(fr, b)}")

    return bad



# Exact diagnostic message per rule (section 9.2). Pinning the full rendered message catches any
# emptied message fragment; one representative violation per rule exercises its message template.
_RULE_MESSAGES = [
    ('HC-A001', 'from honest_type import link\n@link(authorizes=True)\ndef f(x):\n    return x\n', "No AuthProvider registered, but these links declare authorizes=True and cannot be verified: ['f']. Register a provider, or declare authorizes=False."),
    ('HC-A002', "from honest_type import link\n@link(authorizes=True)\ndef f(x):\n    return x\nregister_auth_provider(p)\n", "Link 'f' declares authorizes=True but does not use the boundary-resolved actor ('actor'). Actor identity must come from the boundary, not be trusted from request input."),
    ('HC-OR001', 'from honest_type import orchestrator\n@orchestrator\ndef a():\n    b()\n@orchestrator\ndef b():\n    pass\n', "Orchestrator 'a' calls orchestrator 'b'. Orchestrators do not compose — extract shared logic as a pure helper or a chain."),
    ('HC-OR003', 'from honest_type import orchestrator\n@orchestrator\ndef a():\n    step1()\n    step2()\n    step3()\n@orchestrator\ndef b():\n    step1()\n    step2()\n    step3()\n', "Orchestrators 'a' and 'b' share 3 consecutive operations. Consider extracting the shared sequence as a pure helper (if side-effect-free) or a chain (if I/O is involved). Orchestrators are not composable (HC-OR001)."),
    ('HC-P001', "def f(x):\n    if x == 'a':\n        return 1\n    elif x == 'b':\n        return 2\n    elif x == 'c':\n        return 3\n    return 0\n", 'if/elif/else chain dispatches on value — use dict lookup. See honest-code-principles.md §3.'),
    ('HC-P002', 'def f():\n    try:\n        do()\n    except ValueError:\n        pass\n', "Function 'f' catches an exception in business logic. Let it raise and catch at the boundary (@boundary / route handler), or return a fault as data."),
    ('HC-P003', 'class Widget:\n    pass\n', "Class 'Widget' has no declared base. Honest Code permits class definitions only as subclasses of TypedDict, Protocol, ABC, or a declared Exception. Use a TypedDict for data shapes or a pure function."),
    ('HC-P004', "def f():\n    open('x')\n", "Call 'open' performs I/O or non-deterministic work inside a non-boundary function. Move it to a boundary (decorate @boundary or @link(boundary=True)), or it cannot be verified for purity."),
    ('HC-P005', 'def f(x):\n    return isinstance(x, int)\n', 'isinstance() check in business logic. Consider a vocabulary declaration instead.'),
    ('HC-P006', 'from functools import lru_cache\n@lru_cache\ndef f(x):\n    return x\n', "Cache detected without profiling evidence. Add a @profiled annotation or a '# honest: profiled' comment."),
    ('HC-P007', 'class C:\n    def __init__(self):\n        self._x = 1\n', "Instance state '_x'. Pass as parameter or use context manager."),
    ('HC-P010', 'def f():\n    return Widget(1)\n', "Return value constructs 'Widget', a non-serializable object. A pure function returns a dict or TypedDict, not a class instance."),
    ('HC-P011', "def setup():\n    addEventListener('click', h)\n", "Lifecycle hook 'addEventListener'. Use HTMX attributes or server-rendered HTML."),
    ('HC-P013', "from honest_type import vocabulary, binding, link, predicate\nV = vocabulary({'db': predicate(p)})\nB = binding({'db': 'db_id'})\n@link(accepts=V, binds=B)\ndef f(x):\n    return x\n", "Routing key 'db_id' is bound to predicate recognizer 'db'. A database routing key must be a bounded Set recognizer: the vocabulary is the whitelist, and a predicate lets an arbitrary database identifier reach the pool layer."),
    ('HC-P014', "from honest_type import vocabulary, binding, link\nV = vocabulary({'a': {'x'}, 'b': {'x'}, 'c': {'q'}})\nB = binding({'a': 'slot1', 'b': 'slot2', 'ghost': 'slotg'})\n@link(accepts=V, binds=B)\ndef f(x):\n    return x\n@link(accepts=V, binds=B)\ndef g(x):\n    return x\n", "One recognizer is shared by types ['a', 'b'] bound to distinct slots ['slot1', 'slot2']. Give each slot a semantically distinct recognizer, or the chain contract cannot catch a swap between them."),
    ('HC-P016', 'def outer():\n    total = 0\n    def inner():\n        nonlocal total\n        total = total + 1\n    return inner\n', "Inner function 'inner' captures ['total'] via nonlocal and mutates it. Closures may not carry mutable state — use pure parameters or move state into persist."),
    ('HC-P017', "def handler(req):\n    return JSONResponse({'ok': True})\n", "Function 'handler' produces HTTP output ('JSONResponse') without being a declared @link with emits vocabulary. Declare emits covering status, content-type, and body shape, or delegate to a serializer link."),
    ('HC-R001', 'from honest_type import link\n@link(accepts=A)\ndef used():\n    return 1\ndef orphan():\n    return 2\n', "Function 'orphan' has no declared role and is not called by any roled function. Declare a role (@link / @recognizer / @boundary / @helper) or remove it."),
    ('HC-SM01', "from honest_type import state_machine, vocabulary\nm = state_machine(states=vocabulary({'s': {'open', 'closed'}}), events=vocabulary({'e': {'shut'}}), initial='open', terminal=['closed'], transitions={('bad', 'badev'): 'closed'})\n", "State 'bad' in transition table not in states vocabulary. Add it to the states vocabulary, or correct the name in the transition."),
    ('HC-SM02', "from honest_type import state_machine, vocabulary\nm = state_machine(states=vocabulary({'s': {'open', 'closed'}}), events=vocabulary({'e': {'shut'}}), initial='open', terminal=['closed'], transitions={('bad', 'badev'): 'closed'})\n", "Event 'badev' in transition table not in events vocabulary. Add it to the events vocabulary, or correct the name in the transition."),
    ('HC-SM03', "from honest_type import state_machine, vocabulary\nm = state_machine(states=vocabulary({'s': {'open', 'closed', 'island'}}), events=vocabulary({'e': {'shut'}}), initial='open', terminal=['closed'], transitions={('open', 'shut'): 'closed'})\n", "State 'island' is unreachable. Add a transition that reaches it, or remove the state."),
    ('HC-SM04', "from honest_type import state_machine, vocabulary\nm = state_machine(states=vocabulary({'s': {'open', 'closed', 'island'}}), events=vocabulary({'e': {'shut'}}), initial='open', terminal=['closed'], transitions={('open', 'shut'): 'closed'})\n", "State 'island' has no outgoing transitions and is not declared terminal. Add a transition out of it, or declare it a terminal state."),
    ('HC-SM05', "from honest_type import state_machine, vocabulary\nm = state_machine(states=vocabulary({'s': {'open', 'closed'}}), events=vocabulary({'e': {'shut'}}), initial='ghost', terminal=['closed'], transitions={('open', 'shut'): 'closed'})\n", "Initial state 'ghost' not in states vocabulary. Add it to the states vocabulary, or correct the initial-state name."),
    ('HC-SYN', 'def f(x):\n    if (x ==):\n        pass\n', 'Source does not parse. Fix the syntax error at this location so the file can be parsed.'),
    ('HC001', 'from honest_type import chain\ndef step(x):\n    return x\nc = chain(step)\n', "Function 'step' in chain has no vocabulary declared. Wrap with @link(accepts=..., emits=...)."),
    ('HC002', "from honest_type import vocabulary, link, chain\nA = vocabulary({'a': {'x'}})\nB = vocabulary({'b': {'y'}})\n@link(accepts=A, emits=A)\ndef first(x):\n    return x\n@link(accepts=B, emits=B)\ndef second(x):\n    return x\nc = chain(first, second)\n", "Link 'second' accepts types not provided by previous link 'first': ['b']. Emit those types from the previous link, or drop them from this link's accepts."),
    ('HC003', "from honest_type import vocabulary\nV = vocabulary({'a': {'x', 'y'}, 'b': {'y', 'z'}})\n", "Types 'a' and 'b' share values: ['y']. Make their value sets disjoint, or merge the types."),
    ('HC004', "from honest_type import vocabulary, binding, link\nV = vocabulary({'a': {'x'}, 'b': {'y'}})\nB = binding({'a': 'slot1'})\n@link(accepts=V, binds=B)\ndef f(x):\n    return x\n", "Type 'b' defined in vocabulary 'V' but never bound or composed. Bind it in a binding table or compose it into another type, or remove it from the vocabulary."),
    ('HC005', "from honest_type import vocabulary, binding, link\nV = vocabulary({'a': {'x'}})\nB = binding({'a': 'slot1', 'ghost': 'slot2'})\n@link(accepts=V, binds=B)\ndef f(x):\n    return x\n", "Binding 'B' references type 'ghost' not found in vocabulary 'V'. Add the type to the vocabulary, or correct the name in the binding."),
    ('HC006', "from honest_type import vocabulary, composed\nV = vocabulary({'a': {'x'}}, composed_types=[composed('combo', requires={'ghost': 1})])\n", "Composed type 'combo' requires unknown base type 'ghost'. Declare the base type in the vocabulary, or correct its name."),
    ('HC007', 'from honest_type import chain\nc = chain()\n', "Chain 'c' has no links. Add at least one @link to the chain, or remove the chain."),
    ('HC008', "from honest_type import link\n@link(accepts=A, emits=B)\ndef f(x):\n    open('x')\n", "Link 'f' may be impure: ['open']. Add boundary=True if the I/O is intentional."),
    ('HC009', "from honest_type import vocabulary, predicate\nV = vocabulary({'a': predicate(lambda s: int(s) > 0)})\n", "Predicate 'a' may throw on non-matching input: ['int()']. Guard the access or wrap in try/except."),
    ('HC010', "from honest_type import vocabulary, binding, link\nA = vocabulary({'a': {'x'}})\nB = vocabulary({'a': {'x'}, 'b': {'y'}})\nBind = binding({'b': 'slot_b'})\n@link(accepts=A, emits=B, binds=Bind)\ndef f(x):\n    return x\n", "Link 'f' declares emission of types never produced: ['b']. Remove them from the link's emits, or produce them in the body."),
    ('HC011', "from honest_type import vocabulary, predicate\nV = vocabulary({'a': predicate(p)})\n", "Catch-all check for predicate type 'a' requires sampling and is verified by honest-test."),
]

def _probe_rule_messages() -> list[str]:
    """Pin the exact diagnostic message of each rule. The cases above assert which rule fires; this
    asserts the full message text, so emptying any message fragment is caught."""
    bad = []
    for rule, source, message in _RULE_MESSAGES:
        msgs = [d["message"] for d in check_source(source, "f.py") if d["rule"] == rule]
        if message not in msgs:
            bad.append(f"{rule} message drifted: expected {message!r}, got {msgs}")
    return bad


# --- Vocabulary-member and conditional-branch coverage (section 9.6): one case per bounded-set
# member so emptying any member is caught, plus the conditional message branches. ---
_case("p004_mut_append", "d = {}\nd.append()\ndef f():\n    return d\n", must_fire=("HC-P004",))
_case("p004_mut_add", "d = {}\nd.add()\ndef f():\n    return d\n", must_fire=("HC-P004",))
_case("p004_mut_update", "d = {}\nd.update()\ndef f():\n    return d\n", must_fire=("HC-P004",))
_case("p004_mut_pop", "d = {}\nd.pop()\ndef f():\n    return d\n", must_fire=("HC-P004",))
_case("p004_mut_popitem", "d = {}\nd.popitem()\ndef f():\n    return d\n", must_fire=("HC-P004",))
_case("p004_mut_clear", "d = {}\nd.clear()\ndef f():\n    return d\n", must_fire=("HC-P004",))
_case("p004_mut_insert", "d = {}\nd.insert()\ndef f():\n    return d\n", must_fire=("HC-P004",))
_case("p004_mut_remove", "d = {}\nd.remove()\ndef f():\n    return d\n", must_fire=("HC-P004",))
_case("p004_mut_extend", "d = {}\nd.extend()\ndef f():\n    return d\n", must_fire=("HC-P004",))
_case("p004_mut_setdefault", "d = {}\nd.setdefault()\ndef f():\n    return d\n", must_fire=("HC-P004",))
_case("p004_mut_discard", "d = {}\nd.discard()\ndef f():\n    return d\n", must_fire=("HC-P004",))
_case("p004_mut_sort", "d = {}\nd.sort()\ndef f():\n    return d\n", must_fire=("HC-P004",))
_case("p004_mut_reverse", "d = {}\nd.reverse()\ndef f():\n    return d\n", must_fire=("HC-P004",))
_case("p004_listcomp", "c = [x for x in y]\nc.append(1)\ndef f():\n    return c\n", must_fire=("HC-P004",))
_case("p004_setcomp", "c = {x for x in y}\nc.add(1)\ndef f():\n    return c\n", must_fire=("HC-P004",))
_case("p004_dictcomp", "c = {k: v for k, v in y}\nc.clear()\ndef f():\n    return c\n", must_fire=("HC-P004",))
_case("p006_cache_cache", "@cache\ndef f(self):\n    return 1\n", must_fire=("HC-P006",))
_case("p006_cache_memoize", "@memoize\ndef f(self):\n    return 1\n", must_fire=("HC-P006",))
_case("p006_cache_cached_property", "@cached_property\ndef f(self):\n    return 1\n", must_fire=("HC-P006",))
_case("p011_useEffect", "def setup():\n    useEffect(h)\n", must_fire=("HC-P011",))
_case("p011_useLayoutEffect", "def setup():\n    useLayoutEffect(h)\n", must_fire=("HC-P011",))
_case("p011_removeEventListener", "def setup():\n    removeEventListener(h)\n", must_fire=("HC-P011",))
_case("p011_ngOnInit", "def setup():\n    ngOnInit(h)\n", must_fire=("HC-P011",))
_case("p011_ngOnDestroy", "def setup():\n    ngOnDestroy(h)\n", must_fire=("HC-P011",))
_case("p011_componentDidMount", "def setup():\n    componentDidMount(h)\n", must_fire=("HC-P011",))
_case("p011_componentDidUpdate", "def setup():\n    componentDidUpdate(h)\n", must_fire=("HC-P011",))
_case("p011_componentWillUnmount", "def setup():\n    componentWillUnmount(h)\n", must_fire=("HC-P011",))
_case("p013_tenant_id", "from honest_type import vocabulary, binding, link, predicate\nV = vocabulary({'k': predicate(p)})\nB = binding({'k': 'tenant_id'})\n@link(accepts=V, binds=B)\ndef f(x):\n    return x\n", must_fire=("HC-P013",))
_case("p013_credential", "from honest_type import vocabulary, binding, link, predicate\nV = vocabulary({'k': predicate(p)})\nB = binding({'k': 'credential'})\n@link(accepts=V, binds=B)\ndef f(x):\n    return x\n", must_fire=("HC-P013",))
_case("hc009_float", "from honest_type import vocabulary, predicate\nV = vocabulary({'a': predicate(lambda s: float(s) > 0)})\n", must_fire=("HC009",))
_case("hc009_index", "from honest_type import vocabulary, predicate\nV = vocabulary({'a': predicate(lambda s: s[0])})\n", must_fire=("HC009",))
_case("hc009_division", "from honest_type import vocabulary, predicate\nV = vocabulary({'a': predicate(lambda s: s / 2)})\n", must_fire=("HC009",))
_case("p003_base_ABC", "class C(ABC):\n    pass\n", must_not_fire=("HC-P003",))
_case("p003_base_Exception", "class C(Exception):\n    pass\n", must_not_fire=("HC-P003",))
_case("p003_base_BaseException", "class C(BaseException):\n    pass\n", must_not_fire=("HC-P003",))
_case("p003_base_Error", "class C(Error):\n    pass\n", must_not_fire=("HC-P003",))
_case("hc004_requires_keeps_type", "from honest_type import vocabulary, binding, link, composed\nV = vocabulary({'a': {'x'}, 'b': {'y'}}, composed_types=[composed('combo', requires={'b': 1})])\nB = binding({'a': 's1'})\n@link(accepts=V, binds=B)\ndef f(x):\n    return x\n", must_not_fire=("HC004",))
_case("hc004_captures_keeps_type", "from honest_type import vocabulary, binding, link, composed\nV = vocabulary({'a': {'x'}, 'b': {'y'}}, composed_types=[composed('combo', captures='b')])\nB = binding({'a': 's1'})\n@link(accepts=V, binds=B)\ndef f(x):\n    return x\n", must_not_fire=("HC004",))
_case("p004_boundary_link_io_clean", "from honest_type import link\n@link(accepts=A, emits=B, boundary=True)\ndef f(x):\n    open('x')\n", must_not_fire=("HC-P004", "HC008"))
# A pairing whose binding name is undefined must be skipped cleanly by every pairing rule (the
# `vocab not in vocabularies or binding not in bindings` guard); without it, indexing bindings raises.
_case("pairing_undefined_binding_clean", "from honest_type import vocabulary, link\nV = vocabulary({'a': {'x'}})\n@link(accepts=V, binds=Ghost)\ndef f(x):\n    return x\n")
# Floor division // in a predicate is a risky operation (HC009), like /.
_case("hc009_floordiv", "from honest_type import vocabulary, predicate\nV = vocabulary({'a': predicate(lambda s: s // 2)})\n", must_fire=("HC009",))
# Every HTTP response type is recognised by HC-P017 (a function producing it without a @link/emits).
for _resp in ("Response", "JSONResponse", "HTMLResponse", "PlainTextResponse", "RedirectResponse", "StreamingResponse", "FileResponse"):
    _case(f"p017_{_resp}", f"def h(req):\n    return {_resp}(x)\n", must_fire=("HC-P017",))
# A cache annotated '# honest: profiled' is exempt from HC-P006 (the profiled-comment detector).
_case("p006_profiled_exempt", "from functools import lru_cache\n@lru_cache  # honest: profiled\ndef f(x):\n    return x\n", must_not_fire=("HC-P006",))
# A module container touched only by a non-mutating method (.get) is a constant lookup table, not
# hidden state: HC-P004 must not fire (pins the obj/attr/_MUTATING_METHODS conjunction).
_case("p004_nonmutating_method_clean", "d = {}\nd.get(0)\ndef f():\n    return d\n", must_not_fire=("HC-P004",))
# A parameter shadowing a module-mutable name is local, not hidden state (pins _local_names' parameter walk).
_case("p004_param_shadow_clean", "d = {}\nd[0] = 1\ndef f(d):\n    return d[0]\n", must_not_fire=("HC-P004",))
# Multi-hop reachability: a node reached only through two hops is still reachable (pins the BFS frontier
# append in HC-R001 and HC-SM03 — without it, the second hop is wrongly flagged).
_case("r001_multihop_clean", "from honest_type import link\n@link(accepts=A)\ndef a():\n    b()\ndef b():\n    c()\ndef c():\n    return 1\n", must_not_fire=("HC-R001",))
_case("sm03_multihop_clean", "from honest_type import state_machine, vocabulary\nm = state_machine(states=vocabulary({'s': {'open', 'mid', 'end'}}), events=vocabulary({'e': {'go', 'stop'}}), initial='open', terminal=['end'], transitions={('open', 'go'): 'mid', ('mid', 'stop'): 'end'})\n", must_not_fire=("HC-SM03", "HC-SM04"))
# Module mutation via an augmented subscript assignment (d[0] += 1) is detected (augmented_assignment).
_case("p004_augmented_subscript", "d = {}\nd[0] += 1\ndef f():\n    return d\n", must_fire=("HC-P004",))
# A for-loop tuple-unpack target binds locals (pattern_list/tuple), so a shadowed module name is local.
_case("p004_tuple_unpack_local", "d = {}\nd[0] = 1\ndef f():\n    for d, e in items:\n        pass\n    return 0\n", must_not_fire=("HC-P004",))
# Both boundary decorator forms (@boundary() and @link(boundary = True) with spaces) exempt I/O.
_case("p004_boundary_call_form", "@boundary()\ndef f():\n    open('x')\n", must_not_fire=("HC-P004",))
_case("p004_boundary_spaces", "from honest_type import link\n@link(boundary = True)\ndef f(x):\n    open('x')\n", must_not_fire=("HC-P004",))
# A DECORATED non-boundary link with I/O must still fire HC-P004: pins the boundary-decorator detector
# (emptying its match strings would make every decorated function look like a boundary and suppress it).
_case("p004_decorated_nonboundary_io", "from honest_type import link\n@link(accepts=A, emits=B)\ndef f(x):\n    open('x')\n", must_fire=("HC-P004", "HC008"))
_RULE_MESSAGES += [
    ('HC-P004', 'd = {}\nd.append(1)\ndef f():\n    return d\n', "Reads module-level mutable state 'd' inside a non-boundary function. Module-level mutable state is hidden state — pass it as a parameter or move it into persist."),
    ('HC003', "from honest_type import vocabulary, predicate\nV = vocabulary({'a': predicate(p), 'b': predicate(q)})\n", "Predicate types 'a' and 'b' may overlap — cannot be checked statically; verified by honest-test."),
    ('HC003', "from honest_type import vocabulary, predicate\nV = vocabulary({'a': {'x'}, 'b': predicate(q)})\n", "Set type and predicate type ('a', 'b') may overlap on a Set value — the predicate is not evaluated here; verified by honest-test."),
    ('HC006', "from honest_type import vocabulary, composed\nV = vocabulary({'a': {'x'}}, composed_types=[composed('combo', captures='ghost')])\n", "Composed type 'combo' captures unknown base type 'ghost'. Declare the base type in the vocabulary, or correct its name."),
    ('HC-P003', 'class Widget:  # honest: ignore HC-P003\n    pass\n', 'HC-P003 suppressed by directive.'),
    ('HC009', "from honest_type import vocabulary, predicate\nV = vocabulary({'a': predicate(lambda s: float(s) > 0)})\n", "Predicate 'a' may throw on non-matching input: ['float()']. Guard the access or wrap in try/except."),
    ('HC009', "from honest_type import vocabulary, predicate\nV = vocabulary({'a': predicate(lambda s: s[0])})\n", "Predicate 'a' may throw on non-matching input: ['index']. Guard the access or wrap in try/except."),
    ('HC009', "from honest_type import vocabulary, predicate\nV = vocabulary({'a': predicate(lambda s: s / 2)})\n", "Predicate 'a' may throw on non-matching input: ['division']. Guard the access or wrap in try/except."),
    ('HC-P003', 'class C(Gadget):\n    pass\n', "Class 'C' inherits from 'Gadget'. Use composition over inheritance."),
    ('HC007', 'from honest_type import chain\nchain()\n', "Chain '<anonymous>' has no links. Add at least one @link to the chain, or remove the chain."),
    ('HC-HF001', _FEAT + "def f(state, m):\n    return feature_state(state, 'ghost')\n", "feature_state references 'ghost', which is not a declared flag in FEATURES."),
    ('HC-HF002', _FEAT + _HANDLERS_PARTIAL + "def f(state, m):\n    return HANDLERS[feature_state(state, 'new_checkout')](m)\n", "Handler table 'HANDLERS' is missing an entry for these states of 'new_checkout': ['off']."),
]

# Diagnostic severity per rule (pins the severity literal in each diagnostic() call).
_RULE_SEVERITIES = [
    ("HC011", "info", "from honest_type import vocabulary, predicate\nV = vocabulary({'a': predicate(p)})\n"),
    ("HC008", "warning", "from honest_type import link\n@link(accepts=A, emits=B)\ndef f(x):\n    open('x')\n"),
    ("HC-P010", "error", "def f():\n    return Widget(1)\n"),
    ("HC-P013", "error", "from honest_type import vocabulary, binding, link, predicate\nV = vocabulary({'db': predicate(p)})\nB = binding({'db': 'db_id'})\n@link(accepts=V, binds=B)\ndef f(x):\n    return x\n"),
    ("HC006", "error", "from honest_type import vocabulary, composed\nV = vocabulary({'a': {'x'}}, composed_types=[composed('combo', requires={'ghost': 1})])\n"),
    ("HC-P003", "info", "class Widget:  # honest: ignore HC-P003\n    pass\n"),
]


_RULE_SEVERITIES += [
    ("HC-P004", "error", "CACHE = {}\nCACHE['a'] = 1\ndef f():\n    return CACHE\n"),
    ("HC003", "info", "from honest_type import vocabulary, predicate\nV = vocabulary({'a': predicate(p), 'b': predicate(p)})\n"),
    ("HC003", "info", "from honest_type import vocabulary, predicate\nV = vocabulary({'a': {'x'}, 'b': predicate(p)})\n"),
    ("HC006", "error", "from honest_type import vocabulary, composed\nV = vocabulary({'a': {'x'}}, composed_types=[composed('combo', captures='ghost')])\n"),
    ("HC-HF001", "error", _FEAT + "def f(state, m):\n    return feature_state(state, 'ghost')\n"),
    ("HC-HF002", "warning", _FEAT + _HANDLERS_PARTIAL + "def f(state, m):\n    return HANDLERS[feature_state(state, 'new_checkout')](m)\n"),
]


def _probe_rule_severities() -> list[str]:
    """Pin each diagnostic's severity literal (info downgrade, warning, error)."""
    bad = []
    for rule, severity, source in _RULE_SEVERITIES:
        sevs = [d["severity"] for d in check_source(source, "f.py") if d["rule"] == rule]
        if severity not in sevs:
            bad.append(f"{rule} should emit severity {severity!r}, got {sevs}")
    return bad


# Exact diagnostic count for a source: pins ordering/iteration that would over- or under-report
# (an HC002 reversed comparison, an HC003 branch that double-fires, an HC-P006 missing function guard,
# the HC-SM03 reachability frontier that drops a state).
_COUNT_CASES = [
    ("HC002", "from honest_type import vocabulary, link, chain\nA = vocabulary({'a': {'x'}})\nB = vocabulary({'b': {'y'}})\n@link(accepts=A, emits=A)\ndef first(x):\n    return x\n@link(accepts=B, emits=B)\ndef second(x):\n    return x\nc = chain(first, second)\n", 1),
    ("HC003", "from honest_type import vocabulary, predicate\nV = vocabulary({'a': {'x'}, 'b': predicate(p)})\n", 1),
    ("HC-P006", "@cache\ndef f(self):\n    return 1\n", 1),
    ("HC-SM03", "from honest_type import state_machine, vocabulary\nm = state_machine(states=vocabulary({'s': {'open', 'closed'}}), events=vocabulary({'e': {'shut'}}), initial='ghost', terminal=['closed'], transitions={('open', 'shut'): 'closed'})\n", 2),
]


def _probe_counts() -> list[str]:
    bad = []
    for rule, source, expected in _COUNT_CASES:
        n = sum(1 for d in check_source(source, "f.py") if d["rule"] == rule)
        if n != expected:
            bad.append(f"{rule} should fire {expected} time(s), got {n}")
    # HC-SYN reports the error node's own location, not a (1, 1) fallback.
    syn = [(d["line"], d["col"]) for d in check_source("def f(x):\n    if (x ==):\n        pass\n", "f.py") if d["rule"] == "HC-SYN"]
    if syn != [(2, 11)]:
        bad.append(f"HC-SYN should report the error-node location (2, 11), got {syn}")
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

    for label, source, must_fire, must_not_fire in _JS_CASES:
        total += 1
        fired = _js_rules(source)
        problems = []
        for rule in must_fire:
            if rule not in fired:
                problems.append(f"expected {rule}, got {sorted(set(fired))}")
        for rule in must_not_fire:
            if rule in fired:
                problems.append(f"did not expect {rule}, got {sorted(set(fired))}")
        if problems:
            failed += 1
            print(f"FAIL HC-rule [js:{label}]: {problems}")
        else:
            passed += 1

    total += 1
    javascript_bad = _probe_javascript()
    if javascript_bad:
        failed += 1
        print(f"FAIL HC-rule [javascript]: {javascript_bad}")
    else:
        passed += 1

    total += 1
    helper_bad = _probe_internal_helpers()
    if helper_bad:
        failed += 1
        print(f"FAIL HC-rule [internal_helpers]: {helper_bad}")
    else:
        passed += 1

    total += 1
    extractor_bad = _probe_declgraph_extractors()
    if extractor_bad:
        failed += 1
        print(f"FAIL HC-rule [declgraph_extractors]: {extractor_bad}")
    else:
        passed += 1

    total += 1
    feature_bad = _probe_feature_extractors()
    if feature_bad:
        failed += 1
        print(f"FAIL HC-rule [feature_extractors]: {feature_bad}")
    else:
        passed += 1

    total += 1
    message_bad = _probe_rule_messages()
    if message_bad:
        failed += 1
        print(f"FAIL HC-rule [rule_messages]: {message_bad}")
    else:
        passed += 1

    total += 1
    dedup_bad = _probe_dedup()
    if dedup_bad:
        failed += 1
        print(f"FAIL HC-rule [dedup]: {dedup_bad}")
    else:
        passed += 1

    total += 1
    severity_bad = _probe_rule_severities()
    if severity_bad:
        failed += 1
        print(f"FAIL HC-rule [rule_severities]: {severity_bad}")
    else:
        passed += 1

    total += 1
    count_bad = _probe_counts()
    if count_bad:
        failed += 1
        print(f"FAIL HC-rule [counts]: {count_bad}")
    else:
        passed += 1

    print(f"HC rule laws: {passed} passed, {failed} failed, {total} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run())
