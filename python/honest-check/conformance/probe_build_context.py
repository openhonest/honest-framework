"""Honest probe for honest-check's build_context (feature Scenario: build_context).

build_context is the one pure builder of the per-file CheckContext (section 3.4).
Given real source bytes, a path and the project's declared rule_config, it parses
the source under the grammar honest-parse selects from the path, resolves the
import aliases by calling resolve_aliases, walks the syntax-tree nodes into the
node list, reads the declared function-to-role map, merges honest-check's one
configurable rule's documented value (HC-OR003 min_run = 3) over the project's
declared rule_config, and returns one CheckContext record carrying the parsed
root, the node list, the alias map, the role map, the source bytes, the path and
the resolved per-rule settings.

Each case feeds concrete bytes + path + rule_config and pins the fields the
scenario fixes. The returned source and path are those handed in verbatim. The
resolved rule_config always carries {"HC-OR003": {"min_run": N}}: N = 3 when the
project declared nothing (the documented value merged in), the project's override
otherwise. The alias map is the resolve_aliases result — {"v": "vocabulary"} for a
direct framework import, the empty map when nothing framework is imported (the
explicit absence case). The node list is the full honest-parse walk of the same
source, computed here from a real honest-parse parse as the oracle, never from
build_context itself. A stub returning the seven keys with empty or pass-through
values fails every non-empty case: the empty input rule_config must come back as
{"HC-OR003": {"min_run": 3}}, not {}, and the source/path/aliases must round-trip.
"""
import honest_parse


def _oracle_node_types(source, path):
    """The sorted node-type multiset of a real honest-parse walk of source."""
    parsed = honest_parse.parse_source(source, path)
    root = parsed["ok"].root_node
    return sorted(node.type for node in honest_parse.walk(root))


# Each case: the bytes, path and project-declared rule_config handed to
# build_context, and the context fields the scenario fixes. expect_aliases pins
# the resolve_aliases result; expect_rule_config pins the documented-value merge.
_CASES = [
    {
        "source": b"from honest_type import vocabulary as v\n",
        "path": "mod.py",
        "rule_config": {},
        "expect_rule_config": {"HC-OR003": {"min_run": 3}},
        "expect_aliases": {"v": "vocabulary"},
    },
    {
        # No framework import: resolve_aliases answers the empty map (the explicit
        # absence case). A project override of min_run survives the merge unchanged.
        "source": b"x = 1\n",
        "path": "other.py",
        "rule_config": {"HC-OR003": {"min_run": 5}},
        "expect_rule_config": {"HC-OR003": {"min_run": 5}},
        "expect_aliases": {},
    },
]


def probe_build_context():
    """build_context returns the CheckContext holding the verbatim source and path, the resolved rule_config, the resolve_aliases map and the full node walk."""
    try:
        from honest_check import build_context
    except ImportError as exc:
        return [f"cannot import build_context: {exc}"]

    bad = []
    for case in _CASES:
        ctx = build_context(
            source=case["source"],
            path=case["path"],
            rule_config=case["rule_config"],
        )
        if ctx["source"] != case["source"]:
            bad.append(
                f"build_context({case['source']!r}).source -> {ctx['source']!r}, "
                f"expected {case['source']!r}"
            )
        if ctx["path"] != case["path"]:
            bad.append(
                f"build_context({case['source']!r}).path -> {ctx['path']!r}, "
                f"expected {case['path']!r}"
            )
        if ctx["rule_config"] != case["expect_rule_config"]:
            bad.append(
                f"build_context({case['source']!r}).rule_config -> {ctx['rule_config']!r}, "
                f"expected {case['expect_rule_config']!r}"
            )
        if ctx["aliases"] != case["expect_aliases"]:
            bad.append(
                f"build_context({case['source']!r}).aliases -> {ctx['aliases']!r}, "
                f"expected {case['expect_aliases']!r}"
            )
        got_types = sorted(node.type for node in ctx["nodes"])
        want_types = _oracle_node_types(case["source"], case["path"])
        if not got_types:
            bad.append(
                f"build_context({case['source']!r}).nodes is empty, "
                f"expected the full honest-parse walk ({len(want_types)} nodes)"
            )
        elif got_types != want_types:
            bad.append(
                f"build_context({case['source']!r}).nodes types -> {got_types}, "
                f"expected {want_types}"
            )
    return bad
