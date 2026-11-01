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
