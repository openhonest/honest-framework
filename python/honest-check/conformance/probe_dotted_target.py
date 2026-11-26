# scenario: dotted_target
# inherits: hd=python/honest-check/honest-check.hd::dotted_target -> feature=specs/features/honest-check.feature::dotted_target
"""Honest probe for honest-check's dotted_target (feature Scenario: dotted_target).

dotted_target reads the full dotted name a call invokes — `open`, `os.system`,
`requests.get`, `urllib.request.urlopen` — and NOTHING (None) when the target is
not a plain or dotted name, such as a call on a call's result like `get()(1)`
(HC008). The scenario names these examples outright, so the expected strings are
fixed by it, not chosen here.

Nodes are real tree-sitter nodes parsed by honest-parse; none is fabricated.
"""

from honest_parse import parse, walk


def _ctx(src, language):
    root = parse(src.encode(), language).root_node
    return {
        "root": root,
        "nodes": walk(root),
        "aliases": {},
        "roles": {},
        "source": src.encode(),
        "path": {"python": "probe.py", "ruby": "probe.rb"}[language],
        "rule_config": {"HC-OR003": {"min_run": 3}},
    }


def _first_call(ctx):
    for node in ctx["nodes"]:
        if node.type == "call":
            return node
    return None


# Each case: a call source snippet, and the dotted target dotted_target must return (or None).
_CASES = [
    {"src": "open(f)", "expect": "open"},                               # plain name
    {"src": "os.system(c)", "expect": "os.system"},                     # one-dot name
    {"src": "urllib.request.urlopen(u)", "expect": "urllib.request.urlopen"},  # two-dot name
    {"src": "get()(1)", "expect": None},                                # call on a call's result -> NOTHING
]


def probe_dotted_target():
    """dotted_target returns the full plain-or-dotted call target, else None."""
    try:
        from honest_check import dotted_target
    except ImportError as exc:
        return [f"cannot import dotted_target: {exc}"]

    bad = []
    for case in _CASES:
        ctx = _ctx(case["src"], "python")
        node = _first_call(ctx)
        got = dotted_target(ctx, node)
        if got != case["expect"]:
            bad.append(
                f"dotted_target(<{case['src']!r}>) -> {got!r}, expected {case['expect']!r}"
            )
    ruby = _ctx("Factory.build().run()", "ruby")
    got = dotted_target(ruby, _first_call(ruby))
    if got is not None:
        bad.append(f"dotted_target on a Ruby call with a computed receiver -> {got!r}, expected None")
    return bad
