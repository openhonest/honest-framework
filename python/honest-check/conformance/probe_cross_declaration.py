"""Honest probe for honest-check's cross_declaration (feature Scenario: cross_declaration).

cross_declaration crosses one module's .hd against the whole package of source files and runs
only the crossing rules named in rule_ids. This probe fires every one of the five crossing rules
and pairs each with a clean case that agrees, so each rule's firing is a non-trivial literal no
`return []` stub produces:

- HC-R003: a declared function whose code async-ness disagrees with its declared awaited. The .hd
  declares `handle` as a plain (not-awaited) function; the firing code is `async def handle`, the
  clean code a plain `def handle`.
- HC-R002: an output boundary the .hd marks boundary_out whose body calls a function the .hd marks
  orchestrator. The .hd declares `emit` boundary_out and `run` orchestrator; the firing code has
  `emit` call `run` (an output boundary invoking inward), the clean code has `emit` return a value
  and `run` call `emit` (an orchestrator calling its terminus, allowed).
- HC-R004: a declared function whose code can return the host nothing while its card names no
  absence arm. The .hd declares `find` returning a plain int; the firing code is
  `def find(x): return None`, the clean code `def find(x): return x`. Three more cases hold the
  three-valued reading: `pick` and `look` each name an absence arm and hand their answer back
  through a subscript and a `dict.get` (the `registered_provider` and `resolve_identity` shapes),
  which the checker cannot resolve to present-or-absent, so it fires nothing; `must` names an
  absence arm and provably returns a value every time, which fires the reverse direction.
- HC-R005: a declared value-returning function whose body yields (a generator). The .hd declares
  `items` returning a value; the firing code is `def items(): yield 1`, the clean code
  `def items(): return 1`.
- HC-REF005: an exported function the .hd names nowhere. The .hd declares only `alpha`; the firing
  package defines `alpha` and `beta` with `__all__ = ["alpha", "beta"]`, so `beta` is exported and
  undeclared (§HC-REF005). The clean package defines and exports only the declared `alpha`.

Each declaration is real: honest-design's read_hd parses the .hd text into the Declaration
cross_declaration reads. The package is real: pair_source joins each path to its bytes into a
SourceFile. No fabricated nodes. Each case runs only its own rule via rule_ids, so the rules do
not interfere. A `return []` stub passes every clean case and fails every firing case.
"""

_HD_R003 = (
    "module demo\n\n  layer correctness\n\n"
    '  fn handle : () -> int note "a plain, synchronous function"\n'
)
_HD_R002 = (
    "module demo\n\n  layer correctness\n\n"
    '  boundary_out fn emit : (x: int) -> int note "an output boundary, a terminus"\n'
    '  orchestrator fn run : (x: int) -> int invokes emit note "an orchestrator"\n'
)
_HD_R004 = (
    "module demo\n\n  layer correctness\n\n"
    '  fn find : (x: int) -> int note "its card promises an int, no absence arm"\n'
)
_HD_R005 = (
    "module demo\n\n  layer correctness\n\n"
    '  fn items : () -> int note "its card answers with a value, not a stream"\n'
)
_HD_R004_OPT = (
    "module demo\n\n  layer correctness\n\n"
    '  fn pick : (d: dict<str, int>) -> int | NOTHING note "its card names an absence arm"\n'
)
_HD_R004_OPT_GET = (
    "module demo\n\n  layer correctness\n\n"
    '  fn look : (d: dict<str, int>, k: str) -> int | NOTHING note "its card names an absence arm"\n'
)
_HD_R004_OPT_VALUE = (
    "module demo\n\n  layer correctness\n\n"
    '  fn must : () -> int | NOTHING note "its card names an absence arm it never fills"\n'
)
_HD_R004_NESTED = (
    "module demo\n\n  layer correctness\n\n"
    '  fn gather : (x: int) -> list<str> note "a value card, no absence arm"\n'
)
_HD_REF005 = (
    "module demo\n\n  layer correctness\n\n"
    '  fn alpha : (x: int) -> int note "the one declared function"\n'
)
# A .hd that declares two functions; the code defines only one. declared - defined is
# the allowed lag (the .hd running ahead of the code), so HC-REF005 emits nothing for
# the undefined name (spec §HC-REF005). __all__ exports only the defined function.
_HD_REF005_LAG = (
    "module demo\n\n  layer correctness\n\n"
    '  fn alpha : (x: int) -> int note "defined now"\n'
    '  fn gamma : (x: int) -> int note "declared ahead of the code, not yet written"\n'
)

# Each case: the module's .hd text, its code (bytes), the export module's bytes (the literal
# __all__ HC-REF005 reads), the crossing rule to run, and the verdict crossing it must produce.
_CASES = [
    {
        "desc": "HC-R003: async def over a declaration that does not mark awaited",
        "hd": _HD_R003,
        "source": b"async def handle():\n    return 1\n",
        "export": b"",
        "rule": "HC-R003",
        "must_be_empty": False,
    },
    {
        "desc": "HC-R003 clean: a plain def handle agrees with the declaration",
        "hd": _HD_R003,
        "source": b"def handle():\n    return 1\n",
        "export": b"",
        "rule": "HC-R003",
        "must_be_empty": True,
    },
    {
        "desc": "HC-R002: boundary_out emit calls orchestrator run",
        "hd": _HD_R002,
        "source": b"def emit(x):\n    return run(x)\ndef run(x):\n    return x\n",
        "export": b"",
        "rule": "HC-R002",
        "must_be_empty": False,
    },
    {
        "desc": "HC-R002 clean: emit is a terminus and run calls emit",
        "hd": _HD_R002,
        "source": b"def emit(x):\n    return x\ndef run(x):\n    return emit(x)\n",
        "export": b"",
        "rule": "HC-R002",
        "must_be_empty": True,
    },
    {
        "desc": "HC-R004: find can return None while its card names no absence arm",
        "hd": _HD_R004,
        "source": b"def find(x):\n    return None\n",
        "export": b"",
        "rule": "HC-R004",
        "must_be_empty": False,
    },
    {
        "desc": "HC-R004 clean: find always returns a value",
        "hd": _HD_R004,
        "source": b"def find(x):\n    return x\n",
        "export": b"",
        "rule": "HC-R004",
        "must_be_empty": True,
    },
    {
        "desc": "HC-R004 pass-through subscript: pick names an absence arm and returns d['k']; the checker cannot resolve the value, so it fires nothing (the registered_provider shape)",
        "hd": _HD_R004_OPT,
        "source": b'def pick(d):\n    return d["k"]\n',
        "export": b"",
        "rule": "HC-R004",
        "must_be_empty": True,
    },
    {
        "desc": "HC-R004 pass-through get: look names an absence arm and returns d.get(k); indeterminate, so no finding (the resolve_identity shape)",
        "hd": _HD_R004_OPT_GET,
        "source": b"def look(d, k):\n    return d.get(k)\n",
        "export": b"",
        "rule": "HC-R004",
        "must_be_empty": True,
    },
    {
        "desc": "HC-R004 reverse: must names an absence arm but provably returns a value every time",
        "hd": _HD_R004_OPT_VALUE,
        "source": b"def must():\n    return 1\n",
        "export": b"",
        "rule": "HC-R004",
        "must_be_empty": False,
    },
    {
        "desc": "HC-R004 nested def: gather returns a value and holds an inner helper that returns None; the nested return belongs to the inner function, not gather (the io_monitor shape)",
        "hd": _HD_R004_NESTED,
        "source": b"def gather(x):\n    out = []\n    def restore():\n        return None\n    restore()\n    return out\n",
        "export": b"",
        "rule": "HC-R004",
        "must_be_empty": True,
    },
    {
        "desc": "HC-R004 nested def guard: gather itself returns None with no absence arm while an inner helper returns a value; gather's own None still fires",
        "hd": _HD_R004_NESTED,
        "source": b"def gather(x):\n    def helper():\n        return []\n    helper()\n    return None\n",
        "export": b"",
        "rule": "HC-R004",
        "must_be_empty": False,
    },
    {
        "desc": "HC-R005: items yields while its card returns a value",
        "hd": _HD_R005,
        "source": b"def items():\n    yield 1\n",
        "export": b"",
        "rule": "HC-R005",
        "must_be_empty": False,
    },
    {
        "desc": "HC-R005 clean: items returns a value",
        "hd": _HD_R005,
        "source": b"def items():\n    return 1\n",
        "export": b"",
        "rule": "HC-R005",
        "must_be_empty": True,
    },
    {
        "desc": "HC-REF005: beta is exported and declared in no .hd",
        "hd": _HD_REF005,
        "source": b"def alpha(x):\n    return x\ndef beta(x):\n    return x\n",
        "export": b'__all__ = ["alpha", "beta"]\n',
        "rule": "HC-REF005",
        "must_be_empty": False,
    },
    {
        "desc": "HC-REF005 clean: the package exports exactly the declared alpha",
        "hd": _HD_REF005,
        "source": b"def alpha(x):\n    return x\n",
        "export": b'__all__ = ["alpha"]\n',
        "rule": "HC-REF005",
        "must_be_empty": True,
    },
    {
        "desc": "HC-REF005 allowed lag: gamma is declared but not yet defined; the .hd running ahead of the code emits nothing",
        "hd": _HD_REF005_LAG,
        "source": b"def alpha(x):\n    return x\n",
        "export": b'__all__ = ["alpha"]\n',
        "rule": "HC-REF005",
        "must_be_empty": True,
    },
]


def probe_cross_declaration():
    """cross_declaration fires each crossing rule when code disagrees with the declaration, and is silent when they agree."""
    try:
        from honest_check import cross_declaration, pair_source
    except ImportError as exc:
        return [f"cannot import cross_declaration: {exc}"]

    from honest_design import read_hd

    bad = []
    for case in _CASES:
        parsed = read_hd(case["hd"])
        if "ok" not in parsed:
            bad.append(f"test .hd for {case['desc']} did not parse: {parsed.get('err')}")
            continue
        declaration = parsed["ok"]["modules"][0]
        sources = [pair_source(path="demo.py", text=case["source"])]
        got = cross_declaration(
            sources=sources,
            declaration=declaration,
            export_source=case["export"],
            rule_ids=[case["rule"]],
        )
        ids = [d["rule_id"] for d in got]
        if case["must_be_empty"]:
            if got != []:
                bad.append(
                    f"cross_declaration({case['desc']}) -> {ids}, expected no findings"
                )
        elif case["rule"] not in ids:
            bad.append(
                f"cross_declaration({case['desc']}) -> {ids}, "
                f"expected a {case['rule']} finding"
            )
    return bad
