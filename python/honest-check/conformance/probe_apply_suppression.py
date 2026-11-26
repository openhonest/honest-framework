# scenario: apply_suppression
# inherits: hd=python/honest-check/honest-check.hd::apply_suppression -> feature=specs/features/honest-check.feature::apply_suppression
"""Honest probe for honest-check's apply_suppression (feature Scenario: apply_suppression).

apply_suppression reads the inline suppression directives off the parse in ctx and
applies them to the raw diagnostics: a suppressed finding is downgraded to info
rather than dropped, and an unsuppressed one survives unchanged. Each case builds a
real CheckContext by parsing a Python source with honest-parse, then feeds a raw
diagnostic list. The no-directive case pins that an unsuppressed finding survives
verbatim (a `return []` stub fails it); the directive case pins that a finding
suppressed at its line is downgraded to info (an identity `return raw_diagnostics`
stub fails it).

The directive syntax is the spec's section 7: `# honest: VERB RULE[, RULE...][: reason]`,
verb `ignore` for a single inline line, the reason after the first colon.
"""


def _context(source, path):
    """A real CheckContext over one Python source, built via honest-parse."""
    from honest_parse import parse, walk
    root = parse(source, "python").root_node
    return {
        "root": root,
        "nodes": walk(root),
        "aliases": {},
        "roles": {},
        "source": source,
        "path": path,
        "rule_config": {},
    }


def _diag(severity):
    return {
        "rule_id": "HC-P004",
        "severity": severity,
        "message": "I/O inside a non-boundary function",
        "source_location": "mod.py:1:5",
        "context": "x = get()",
        "fixable": False,
    }


# Each case: a source (parsed into ctx), the raw diagnostics, and the resolved list expected back.
_CASES = [
    # No directive: the unsuppressed finding survives verbatim.
    {
        "source": b"x = get()\n",
        "raw": [_diag("error")],
        "expect": [_diag("error")],
    },
    # Directive on the finding's line suppresses its rule: the finding is downgraded to info.
    {
        "source": b"x = get()  # honest: ignore HC-P004: known io here\n",
        "raw": [_diag("error")],
        "expect": [_diag("info")],
    },
    {
        "source": b"x = get()  # honest: ignore HC-P004, HC-P005: approved exception\n",
        "raw": [
            _diag("error"),
            {**_diag("warning"), "rule_id": "HC-P005"},
            {**_diag("warning"), "rule_id": "HC-P007"},
            {**_diag("error"), "source_location": "mod.py:2:5"},
        ],
        "expect": [
            _diag("info"),
            {**_diag("info"), "rule_id": "HC-P005"},
            {**_diag("warning"), "rule_id": "HC-P007"},
            {**_diag("error"), "source_location": "mod.py:2:5"},
        ],
    },
    {
        "source": b"label = 'ok'\nx = get()  # honest: ignore HC-P004: known I/O\n",
        "path": "group:example.py",
        "raw": [
            {**_diag("error"), "source_location": "group:example.py:2:5"},
            {**_diag("error"), "source_location": "group:example.py:1:5"},
        ],
        "expect": [
            {**_diag("info"), "source_location": "group:example.py:2:5"},
            {**_diag("error"), "source_location": "group:example.py:1:5"},
        ],
    },
    {
        "source": b"x = get()  # note: ignore HC-P004: definitely ordinary prose\n",
        "raw": [_diag("error")],
        "expect": [_diag("error")],
    },
    {
        "source": b"x = get()  # honest: ignore HC-P004\n",
        "raw": [_diag("error")],
        "expect": [_diag("info")],
        "directive_findings": [("HC-SUP002", "error")],
    },
    {
        "source": b"# honest: disable HC-P004\n# honest: enable HC-P004\nx = 1\n",
        "raw": [],
        "expect": [],
        "directive_findings": [("HC-SUP001", "error"), ("HC-SUP002", "error")],
    },
]


def probe_apply_suppression():
    """apply_suppression downgrades a suppressed finding to info and leaves others intact."""
    try:
        from honest_check import apply_suppression
    except ImportError as exc:
        return [f"cannot import apply_suppression: {exc}"]
    try:
        from honest_parse import parse, walk  # noqa: F401 — used by _context
    except ImportError as exc:
        return [f"cannot import honest_parse: {exc}"]

    bad = []
    for case in _CASES:
        ctx = _context(case["source"], case.get("path", "mod.py"))
        got = apply_suppression(ctx=ctx, raw_diagnostics=case["raw"])
        if "directive_findings" in case:
            expected = case["expect"]
            emitted = [(finding["rule_id"], finding["severity"]) for finding in got[len(expected):]]
            if got[:len(expected)] != expected or emitted != case["directive_findings"]:
                bad.append(f"apply_suppression({case['source']!r}) returned {got!r}")
        elif got != case["expect"]:
            bad.append(
                f"apply_suppression(source={case['source']!r}, raw={case['raw']!r}) "
                f"-> {got!r}, expected {case['expect']!r}"
            )
    return bad
