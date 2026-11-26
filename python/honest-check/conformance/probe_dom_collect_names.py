# scenario: dom_collect_names
# inherits: hd=python/honest-check/honest-check.hd::dom_collect_names -> feature=specs/features/honest-check.feature::dom_collect_names
"""Conformance probe for honest-check's dom_collect_names.

Scenario (specs/features/honest-check.feature, Scenario: dom_collect_names):
    Given ctx: CheckContext
    When dom_collect_names is called
    Then it returns the local names this JavaScript file binds to honest-dom's `collect`
    through its own imports, the empty result when the file imports `collect` from no
    honest-dom module, which stands HC-ST002 down.

The honest-dom module specifier and the aliasing shapes are fixed by the state spec
(specs/02-code-quality/honest-state-architecture.md, section 3.2):
    import { collect } from "honest-dom"        -> binds "collect"
    import { collect as read } from "honest-dom" -> binds "read"
A `collect` no honest-dom import binds does not count. The probe parses each JavaScript
file with the real honest-parse grammar and compares the bound names (normalized to a set).
"""

import honest_parse

# Each case: a JavaScript source and the set of local names bound to honest-dom's collect.
_CASES = [
    {"src": 'import { collect } from "honest-dom";', "expect": {"collect"}},
    {"src": 'import { collect as read } from "honest-dom";', "expect": {"read"}},
    {"src": 'import { collect } from "other-lib";', "expect": set()},   # not a honest-dom module
    {"src": "import { collect as saved } from 'honest-dom';", "expect": {"saved"}},
    {"src": 'import { render } from "honest-dom";', "expect": set()},   # honest-dom, but not collect
    {"src": 'const x = 1;', "expect": set()},                          # no imports at all
]


def _ctx(src):
    source = src.encode("utf-8")
    tree = honest_parse.parse(source, "javascript")
    root = tree.root_node
    return {
        "root": root,
        "nodes": honest_parse.walk(root),
        "aliases": {},
        "roles": {},
        "source": source,
        "path": "page.js",
        "rule_config": {"HC-OR003": {"min_run": 3}},
    }


def probe_dom_collect_names():
    """A JavaScript file's imports of honest-dom's collect bind local names (direct or aliased); an import from another module, a non-collect import, or no import binds none (HC-ST002)."""
    try:
        from honest_check import dom_collect_names
    except ImportError as exc:
        return [f"cannot import dom_collect_names: {exc}"]

    bad = []
    for case in _CASES:
        ctx = _ctx(case["src"])
        try:
            got = set(dom_collect_names(ctx))
        except Exception as exc:
            bad.append(f"dom_collect_names({case['src']!r}) raised {exc!r}")
            continue
        if got != case["expect"]:
            bad.append(f"dom_collect_names({case['src']!r}) -> {got!r}, expected {case['expect']!r}")
    return bad
