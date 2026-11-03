"""cross_declaration crosses one module's .hd declaration against the whole
package of source files and returns the declaration-crossing findings as data.

Pins one firing case per crossing rule and one clean case. Each case gives a tiny
valid .hd (parsed through honest-design's read_hd, which is not the function under
test), the package source that disagrees with it, the export module text HC-REF005
reads, and the crossing rules to run. The firing cases assert the expected rule id
fires at severity 'error'; the clean case — every dimension in agreement, all five
rules selected — asserts the empty list. A stub returning [] passes the clean case
but fails all five firing cases.

Spec authorities: §HC-R002 (output boundary invoking inward), §HC-R003 (awaiting
disagreement), §HC-R004 (absence disagreement), §HC-R005 (declared value whose body
yields), §HC-REF005 (declaration and code do not resolve to each other).
"""

# Each case: a declaration .hd, the package sources, the export module text, the
# crossing rules to run, and the rule id expected to fire (None for the clean case).
_CASES = [
    # HC-R002 — emit is declared boundary_out and its code calls orchestrate,
    # declared orchestrator: an output boundary invoking inward.
    {
        "name": "HC-R002 fires",
        "hd": "module m\n\n  boundary_out fn emit : (x: str) -> str\n  orchestrator fn orchestrate : (x: str) -> str\n",
        "sources": [
            {"path": "m.py", "text": "def emit(x):\n    return orchestrate(x)\n\n\ndef orchestrate(x):\n    return x\n"}
        ],
        "export_source": "",
        "rule_ids": ["HC-R002"],
        "want_rule": "HC-R002",
    },
    # HC-R003 — f is declared without awaited; the code defines it async def.
    {
        "name": "HC-R003 fires",
        "hd": "module m\n\n  fn f : (x: str) -> str\n",
        "sources": [{"path": "m.py", "text": "async def f(x):\n    return x\n"}],
        "export_source": "",
        "rule_ids": ["HC-R003"],
        "want_rule": "HC-R003",
    },
    # HC-R004 — g's declared return names no absence arm; the code returns None.
    {
        "name": "HC-R004 fires",
        "hd": "module m\n\n  fn g : (x: str) -> str\n",
        "sources": [{"path": "m.py", "text": "def g(x):\n    return None\n"}],
        "export_source": "",
        "rule_ids": ["HC-R004"],
        "want_rule": "HC-R004",
    },
    # HC-R005 — h is declared to return a value; the code's body yields.
    {
        "name": "HC-R005 fires",
        "hd": "module m\n\n  fn h : (x: str) -> str\n",
        "sources": [{"path": "m.py", "text": "def h(x):\n    yield x\n"}],
        "export_source": "",
        "rule_ids": ["HC-R005"],
        "want_rule": "HC-R005",
    },
    # HC-REF005 — ghost is declared in the .hd and the code has not written it yet. The build
    # order writes the .hd before the code, so a declared-but-unwritten function is the allowed
    # lag and fires nothing; present is written, exported and declared, so it is clean too.
    {
        "name": "HC-REF005 passes a declared-but-unwritten function",
        "hd": "module m\n\n  fn present : (x: str) -> str\n  fn ghost : (x: str) -> str\n",
        "sources": [{"path": "m.py", "text": "def present(x):\n    return x\n"}],
        "export_source": '__all__ = ["present"]\n',
        "rule_ids": ["HC-REF005"],
        "want_rule": None,
    },
    # clean — roles, awaiting, absence, non-generator body and defined/exported
    # names all agree; all five rules selected; no diagnostics.
    {
        "name": "clean agrees",
        "hd": "module m\n\n  fn clean_fn : (x: str) -> str\n",
        "sources": [{"path": "m.py", "text": "def clean_fn(x):\n    return x\n"}],
        "export_source": '__all__ = ["clean_fn"]\n',
        "rule_ids": ["HC-R002", "HC-R003", "HC-R004", "HC-R005", "HC-REF005"],
        "want_rule": None,
    },
    # HC-R004 — a bare `return` (no value) answers nothing, the same as `return None`.
    {
        "name": "HC-R004 fires on a bare return",
        "hd": "module m\n\n  fn g : (x: str) -> str\n",
        "sources": [{"path": "m.py", "text": "def g(x):\n    return\n"}],
        "export_source": "",
        "rule_ids": ["HC-R004"],
        "want_rule": "HC-R004",
    },
    # HC-R002 clean — a boundary_out that calls only a dotted method (non-identifier,
    # skipped) and an undeclared helper (skipped) invokes nothing inward.
    {
        "name": "HC-R002 clean on dotted and undeclared calls",
        "hd": "module m\n\n  boundary_out fn emit : (x: str) -> str\n",
        "sources": [{"path": "m.py", "text": "def emit(x):\n    obj.method()\n    helper(x)\n"}],
        "export_source": "",
        "rule_ids": ["HC-R002"],
        "want_rule": None,
    },
    # HC-R005 clean — a @contextmanager that yields is a context manager, so a yielding
    # body is not a stream-answer and HC-R005 is exempt.
    {
        "name": "HC-R005 exempt for a context manager",
        "hd": "module m\n\n  fn h : (x: str) -> str\n",
        "sources": [{"path": "m.py", "text": "@contextmanager\ndef h(x):\n    yield x\n"}],
        "export_source": "",
        "rule_ids": ["HC-R005"],
        "want_rule": None,
    },
    # A source file that does not parse contributes no facts (a parse failure is HC-SYN's,
    # not this core's); the valid file's boundary_out is clean under HC-R002.
    {
        "name": "a non-parsing source file contributes nothing",
        "hd": "module m\n\n  boundary_out fn emit : (x: str) -> str\n",
        "sources": [
            {"path": "bad.py", "text": "def (:\n"},
            {"path": "m.py", "text": "def emit(x):\n    return x\n"},
        ],
        "export_source": "",
        "rule_ids": ["HC-R002"],
        "want_rule": None,
    },
    # HC-REF005 — an empty export source carries no literal __all__, so the surface is
    # inferred, not declared, and the rule cannot read it.
    {
        "name": "HC-REF005 fires on an empty export source",
        "hd": "module m\n\n  fn clean_fn : (x: str) -> str\n",
        "sources": [{"path": "m.py", "text": "def clean_fn(x):\n    return x\n"}],
        "export_source": "",
        "rule_ids": ["HC-REF005"],
        "want_rule": "HC-REF005",
    },
    # HC-REF005 — an export source that does not parse carries no readable __all__.
    {
        "name": "HC-REF005 fires on a non-parsing export source",
        "hd": "module m\n\n  fn clean_fn : (x: str) -> str\n",
        "sources": [{"path": "m.py", "text": "def clean_fn(x):\n    return x\n"}],
        "export_source": "def (:\n",
        "rule_ids": ["HC-REF005"],
        "want_rule": "HC-REF005",
    },
    # HC-REF005 — an export source whose only assignment is not __all__ declares no surface.
    {
        "name": "HC-REF005 fires when no __all__ is assigned",
        "hd": "module m\n\n  fn clean_fn : (x: str) -> str\n",
        "sources": [{"path": "m.py", "text": "def clean_fn(x):\n    return x\n"}],
        "export_source": "other = [1]\n",
        "rule_ids": ["HC-REF005"],
        "want_rule": "HC-REF005",
    },
    # HC-REF005 — an __all__ built by a call, not a literal list, is not a declared surface.
    {
        "name": "HC-REF005 fires on a non-literal __all__",
        "hd": "module m\n\n  fn clean_fn : (x: str) -> str\n",
        "sources": [{"path": "m.py", "text": "def clean_fn(x):\n    return x\n"}],
        "export_source": "__all__ = build()\n",
        "rule_ids": ["HC-REF005"],
        "want_rule": "HC-REF005",
    },
    # HC-REF005 — a name exported but declared in no .hd, alongside a non-identifier
    # module assignment that the __all__ scan passes over.
    {
        "name": "HC-REF005 fires on an exported name the .hd does not declare",
        "hd": "module m\n\n  fn present : (x: str) -> str\n",
        "sources": [{"path": "m.py", "text": "def present(x):\n    return x\n"}],
        "export_source": 'a.b = 1\n__all__ = ["present", "extra"]\n',
        "rule_ids": ["HC-REF005"],
        "want_rule": "HC-REF005",
    },
    # HC-REF005 — a declared-and-defined name whose code parameter count disagrees with the
    # declared parameter count.
    {
        "name": "HC-REF005 fires on an arity disagreement",
        "hd": "module m\n\n  fn present : (x: str) -> str\n",
        "sources": [{"path": "m.py", "text": "def present(x, y):\n    return x\n"}],
        "export_source": '__all__ = ["present"]\n',
        "rule_ids": ["HC-REF005"],
        "want_rule": "HC-REF005",
    },
    # HC-R004 clean — an undeclared code function that returns None is skipped (the rule
    # crosses only declared functions); the declared function agrees.
    {
        "name": "HC-R004 skips an undeclared function",
        "hd": "module m\n\n  fn present : (x: str) -> str\n",
        "sources": [
            {"path": "m.py", "text": "def present(x):\n    return x\n\n\ndef extra(x):\n    return None\n"}
        ],
        "export_source": "",
        "rule_ids": ["HC-R004"],
        "want_rule": None,
    },
    # A rule id the crossing table does not name is not a crossing rule and is skipped;
    # the real HC-R002 rule runs clean, so the result is empty.
    {
        "name": "an unknown rule id is skipped",
        "hd": "module m\n\n  boundary_out fn emit : (x: str) -> str\n",
        "sources": [{"path": "m.py", "text": "def emit(x):\n    return x\n"}],
        "export_source": "",
        "rule_ids": ["HC-R002", "BOGUS"],
        "want_rule": None,
    },
    # A declared function with a nested def: the crossing walk reads the function's own
    # body without descending into the nested def, so the clean function stays clean.
    {
        "name": "a nested def body is not read as the function's own",
        "hd": "module m\n\n  fn present : (x: str) -> str\n",
        "sources": [
            {"path": "m.py", "text": "def present(x):\n    def inner():\n        return x\n    return x\n"}
        ],
        "export_source": "",
        "rule_ids": ["HC-R002"],
        "want_rule": None,
    },
    # A decorated top-level node that is not a function (a decorated class) contributes
    # no code fact; the declared function is still crossed clean.
    {
        "name": "a decorated non-function top node contributes nothing",
        "hd": "module m\n\n  fn present : (x: str) -> str\n",
        "sources": [
            {"path": "m.py", "text": "@deco\nclass C:\n    pass\n\n\ndef present(x):\n    return x\n"}
        ],
        "export_source": "",
        "rule_ids": ["HC-R002"],
        "want_rule": None,
    },
]



# ---- full-record pinning: the probe above asserts only (rule_id, severity)
# and the offending path; these cases pin the whole Diagnostic record of each
# variant, so emptying a message/key literal, flipping fixable, or swapping a
# dict key changes the record and fails here.
_MSG_CASES = [
    {
        "id": 'HC-R002',
        "hd": 'module m\n\n  boundary_out fn emit : (x: str) -> str\n  orchestrator fn orchestrate : (x: str) -> str\n',
        "sources": [{'path': 'm.py', 'text': 'def emit(x):\n    return orchestrate(x)\n\n\ndef orchestrate(x):\n    return x\n'}],
        "export_source": '',
        "rule_ids": ['HC-R002'],
        "expected": [{'rule_id': 'HC-R002', 'severity': 'error', 'message': "'emit' is declared boundary_out and invokes 'orchestrate', declared orchestrator. An output boundary is a terminus: return a value the caller acts on, or move the work upstream of the boundary.", 'source_location': 'm.py:1:1', 'context': '', 'fixable': False}],
    },
    {
        "id": 'HC-R003-async',
        "hd": 'module m\n\n  fn f : (x: str) -> str\n',
        "sources": [{'path': 'm.py', 'text': 'async def f(x):\n    return x\n'}],
        "export_source": '',
        "rule_ids": ['HC-R003'],
        "expected": [{'rule_id': 'HC-R003', 'severity': 'error', 'message': "'f' is async def and its declaration does not say awaited.", 'source_location': 'm.py:1:1', 'context': '', 'fixable': False}],
    },
    {
        "id": 'HC-R003-awaited-plain',
        "hd": 'module m\n\n  fn f : (x: str) -> str awaited\n',
        "sources": [{'path': 'm.py', 'text': 'def f(x):\n    return x\n'}],
        "export_source": '',
        "rule_ids": ['HC-R003'],
        "expected": [{'rule_id': 'HC-R003', 'severity': 'error', 'message': "'f' is declared awaited and is a plain def.", 'source_location': 'm.py:1:1', 'context': '', 'fixable': False}],
    },
    {
        "id": 'HC-R004-none',
        "hd": 'module m\n\n  fn g : (x: str) -> str\n',
        "sources": [{'path': 'm.py', 'text': 'def g(x):\n    return None\n'}],
        "export_source": '',
        "rule_ids": ['HC-R004'],
        "expected": [{'rule_id': 'HC-R004', 'severity': 'error', 'message': "'g' can return None and its card names no absence arm. Add '| NOTHING' to the return, or stop returning None.", 'source_location': 'm.py:1:1', 'context': '', 'fixable': False}],
    },
    {
        "id": 'HC-R004-absence',
        "hd": 'module m\n\n  fn g : (x: str) -> str | NOTHING\n',
        "sources": [{'path': 'm.py', 'text': 'def g(x):\n    return x\n'}],
        "export_source": '',
        "rule_ids": ['HC-R004'],
        "expected": [{'rule_id': 'HC-R004', 'severity': 'error', 'message': "'g' is declared to return an absence and never returns None. Remove the absence arm, or return None where the answer is absent.", 'source_location': 'm.py:1:1', 'context': '', 'fixable': False}],
    },
    {
        "id": 'HC-R004-absent-atom',
        "hd": 'module m\n\n  fn g : (x: str) -> str | Absent\n',
        "sources": [{'path': 'm.py', 'text': 'def g(x):\n    return x\n'}],
        "export_source": '',
        "rule_ids": ['HC-R004'],
        "expected": [{'rule_id': 'HC-R004', 'severity': 'error', 'message': "'g' is declared to return an absence and never returns None. Remove the absence arm, or return None where the answer is absent.", 'source_location': 'm.py:1:1', 'context': '', 'fixable': False}],
    },
    {
        "id": 'HC-R005',
        "hd": 'module m\n\n  fn h : (x: str) -> str\n',
        "sources": [{'path': 'm.py', 'text': 'def h(x):\n    yield x\n'}],
        "export_source": '',
        "rule_ids": ['HC-R005'],
        "expected": [{'rule_id': 'HC-R005', 'severity': 'error', 'message': "'h' is declared and its body yields, so it answers with a stream rather than a value. Return a value, or move the laziness into a helper this module does not declare.", 'source_location': 'm.py:1:1', 'context': '', 'fixable': False}],
    },
    {
        "id": 'unwrap-decorated-async',
        "hd": 'module m\n\n  fn f : (x: str) -> str\n',
        "sources": [{'path': 'm.py', 'text': '@deco\nasync def f(x):\n    return x\n'}],
        "export_source": '',
        "rule_ids": ['HC-R003'],
        "expected": [{'rule_id': 'HC-R003', 'severity': 'error', 'message': "'f' is async def and its declaration does not say awaited.", 'source_location': 'm.py:2:1', 'context': '', 'fixable': False}],
    },
    {
        "id": 'check_r002-boundary-in',
        "hd": 'module m\n\n  boundary_out fn emit : (x: str) -> str\n  boundary_in fn inward : (x: str) -> str\n',
        "sources": [{'path': 'm.py', 'text': 'def emit(x):\n    return inward(x)\n\n\ndef inward(x):\n    return x\n'}],
        "export_source": '',
        "rule_ids": ['HC-R002'],
        "expected": [{'rule_id': 'HC-R002', 'severity': 'error', 'message': "'emit' is declared boundary_out and invokes 'inward', declared boundary_in. An output boundary is a terminus: return a value the caller acts on, or move the work upstream of the boundary.", 'source_location': 'm.py:1:1', 'context': '', 'fixable': False}],
    },
    {
        "id": 'literal_all-tuple',
        "hd": 'module m\n\n  fn present : (x: str) -> str\n',
        "sources": [{'path': 'm.py', 'text': 'def present(x):\n    return x\n'}],
        "export_source": '__all__ = ("present",)\n',
        "rule_ids": ['HC-REF005'],
        "expected": [],
    },
    {
        "id": 'literal_all-set',
        "hd": 'module m\n\n  fn present : (x: str) -> str\n',
        "sources": [{'path': 'm.py', 'text': 'def present(x):\n    return x\n'}],
        "export_source": '__all__ = {"present"}\n',
        "rule_ids": ['HC-REF005'],
        "expected": [],
    },
    {
        "id": 'literal_all-annot-noall',
        "hd": 'module m\n\n  fn present : (x: str) -> str\n',
        "sources": [{'path': 'm.py', 'text': 'def present(x):\n    return x\n'}],
        "export_source": 'a, b = 1, 2\n__all__: list\n',
        "rule_ids": ['HC-REF005'],
        "expected": [{'rule_id': 'HC-REF005', 'severity': 'error', 'message': 'the module publishes no literal export list, so its surface is inferred rather than declared and this rule cannot read it. Write the list.', 'source_location': 'm.py', 'context': '', 'fixable': False}],
    },
    {
        "id": 'literal_all-augmented',
        "hd": 'module m\n\n  fn present : (x: str) -> str\n',
        "sources": [{'path': 'm.py', 'text': 'def present(x):\n    return x\n'}],
        "export_source": '__all__ += ["present"]\n',
        "rule_ids": ['HC-REF005'],
        "expected": [{'rule_id': 'HC-REF005', 'severity': 'error', 'message': 'the module publishes no literal export list, so its surface is inferred rather than declared and this rule cannot read it. Write the list.', 'source_location': 'm.py', 'context': '', 'fixable': False}],
    },
    {
        "id": 'check_r002-role-filter',
        "hd": 'module m\n\n  orchestrator fn emit : (x: str) -> str\n  boundary_in fn inward : (x: str) -> str\n',
        "sources": [{'path': 'm.py', 'text': 'def emit(x):\n    return inward(x)\n\n\ndef inward(x):\n    return x\n'}],
        "export_source": '',
        "rule_ids": ['HC-R002'],
        "expected": [],
    },
    {
        # With no sources, module_root falls back to "exports.py"; present is declared but not
        # yet written (the allowed lag, no finding), while ghost is exported and declared in no
        # .hd, so the exported-not-declared finding reports at that fallback location.
        "id": 'check_ref005-module-root',
        "hd": 'module m\n\n  fn present : (x: str) -> str\n',
        "sources": [],
        "export_source": '__all__ = ["present", "ghost"]\n',
        "rule_ids": ['HC-REF005'],
        "expected": [{'rule_id': 'HC-REF005', 'severity': 'error', 'message': "'ghost' is exported by the module and declared in no .hd. Declare it, or stop exporting it.", 'source_location': 'exports.py', 'context': '', 'fixable': False}],
    },
    {
        "id": 'check_ref005-module-root-first',
        "hd": 'module m\n\n  fn ghost : (x: str) -> str\n',
        "sources": [{'path': 'a.py', 'text': 'def present(x):\n    return x\n'}, {'path': 'b.py', 'text': 'y = 1\n'}],
        "export_source": 'x = 1\n',
        "rule_ids": ['HC-REF005'],
        "expected": [{'rule_id': 'HC-REF005', 'severity': 'error', 'message': 'the module publishes no literal export list, so its surface is inferred rather than declared and this rule cannot read it. Write the list.', 'source_location': 'a.py', 'context': '', 'fixable': False}],
    },
    {
        "id": 'arity-comment-param',
        "hd": 'module m\n\n  fn present : (x: str) -> str\n',
        "sources": [{'path': 'm.py', 'text': 'def present(\n    x,  # c\n):\n    return x\n'}],
        "export_source": '__all__ = ["present"]\n',
        "rule_ids": ['HC-REF005'],
        "expected": [],
    },
    {
        "id": 'cross-gather-nested-none',
        "hd": 'module m\n\n  fn g : (x: str) -> str\n',
        "sources": [{'path': 'm.py', 'text': 'def g(x):\n    def inner():\n        return None\n    return x\n'}],
        "export_source": '',
        "rule_ids": ['HC-R004'],
        "expected": [],
    },
    {
        "id": 'contextmanager-not',
        "hd": 'module m\n\n  fn present : (x: str) -> str\n',
        "sources": [{'path': 'm.py', 'text': '@other\ndef present(x):\n    yield x\n'}],
        "export_source": '',
        "rule_ids": ['HC-R005'],
        "expected": [{'rule_id': 'HC-R005', 'severity': 'error', 'message': "'present' is declared and its body yields, so it answers with a stream rather than a value. Return a value, or move the laziness into a helper this module does not declare.", 'source_location': 'm.py:2:1', 'context': '', 'fixable': False}],
    },
    {
        "id": 'HC-REF005-no-all',
        "hd": 'module m\n\n  fn clean_fn : (x: str) -> str\n',
        "sources": [{'path': 'm.py', 'text': 'def clean_fn(x):\n    return x\n'}],
        "export_source": '',
        "rule_ids": ['HC-REF005'],
        "expected": [{'rule_id': 'HC-REF005', 'severity': 'error', 'message': 'the module publishes no literal export list, so its surface is inferred rather than declared and this rule cannot read it. Write the list.', 'source_location': 'm.py', 'context': '', 'fixable': False}],
    },
    {
        "id": 'HC-REF005-exported-undeclared',
        "hd": 'module m\n\n  fn present : (x: str) -> str\n',
        "sources": [{'path': 'm.py', 'text': 'def present(x):\n    return x\n'}],
        "export_source": '__all__ = ["present", "extra"]\n',
        "rule_ids": ['HC-REF005'],
        "expected": [{'rule_id': 'HC-REF005', 'severity': 'error', 'message': "'extra' is exported by the module and declared in no .hd. Declare it, or stop exporting it.", 'source_location': 'm.py', 'context': '', 'fixable': False}],
    },
    {
        # ghost is declared and not yet written: the allowed lag, so the record is empty.
        "id": 'HC-REF005-declared-unwritten',
        "hd": 'module m\n\n  fn present : (x: str) -> str\n  fn ghost : (x: str) -> str\n',
        "sources": [{'path': 'm.py', 'text': 'def present(x):\n    return x\n'}],
        "export_source": '__all__ = ["present"]\n',
        "rule_ids": ['HC-REF005'],
        "expected": [],
    },
    {
        "id": 'HC-REF005-arity',
        "hd": 'module m\n\n  fn present : (x: str) -> str\n',
        "sources": [{'path': 'm.py', 'text': 'def present(x, y):\n    return x\n'}],
        "export_source": '__all__ = ["present"]\n',
        "rule_ids": ['HC-REF005'],
        "expected": [{'rule_id': 'HC-REF005', 'severity': 'error', 'message': "'present' is declared with 1 parameters and defined with 2.", 'source_location': 'm.py:1:1', 'context': '', 'fixable': False}],
    },
]

def _canon(diags):
    import json
    return sorted(json.dumps(d, sort_keys=True) for d in diags)


def _message_failures():
    from honest_check import cross_declaration
    from honest_design import read_hd
    bad = []
    for case in _MSG_CASES:
        declaration = read_hd(case["hd"])["ok"]["modules"][0]
        got = cross_declaration(case["sources"], declaration, case["export_source"], case["rule_ids"])
        if _canon(got) != _canon(case["expected"]):
            bad.append(f"record pinning {case['id']!r}: got {_canon(got)}, expected {_canon(case['expected'])}")
    return bad

def probe_cross_declaration():
    try:
        from honest_check import cross_declaration
    except ImportError as exc:
        return [f"cannot import cross_declaration: {exc}"]
    from honest_design import read_hd

    bad = []
    for case in _CASES:
        parsed = read_hd(case["hd"])
        if "ok" not in parsed:
            bad.append(f"{case['name']}: fixture .hd did not parse: {parsed.get('err')!r}")
            continue
        declaration = parsed["ok"]["modules"][0]

        got = cross_declaration(
            case["sources"], declaration, case["export_source"], case["rule_ids"]
        )
        if not isinstance(got, list):
            bad.append(f"{case['name']}: cross_declaration -> {got!r}, expected a list")
            continue

        if case["want_rule"] is None:
            if got != []:
                bad.append(f"{case['name']}: cross_declaration -> {got!r}, expected [] (clean)")
            continue

        fired = [d for d in got if d.get("rule_id") == case["want_rule"]]
        if not fired:
            rule_ids = [d.get("rule_id") for d in got]
            bad.append(
                f"{case['name']}: cross_declaration -> rule_ids {rule_ids}, "
                f"expected one to be {case['want_rule']!r}"
            )
        elif not any(d.get("severity") == "error" for d in fired):
            bad.append(
                f"{case['name']}: {case['want_rule']} fired at severity "
                f"{[d.get('severity') for d in fired]}, expected 'error'"
            )
    bad.extend(_message_failures())
    return bad
