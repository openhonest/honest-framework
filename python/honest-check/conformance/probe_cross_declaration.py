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
    # HC-REF005 — ghost is declared and defined nowhere across the sources.
    {
        "name": "HC-REF005 fires",
        "hd": "module m\n\n  fn present : (x: str) -> str\n  fn ghost : (x: str) -> str\n",
        "sources": [{"path": "m.py", "text": "def present(x):\n    return x\n"}],
        "export_source": '__all__ = ["present"]\n',
        "rule_ids": ["HC-REF005"],
        "want_rule": "HC-REF005",
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
    return bad
