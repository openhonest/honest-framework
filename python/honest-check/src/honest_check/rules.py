"""Rule registry and the check_source entry point (sections 4, 8).

The composition root of honest-check. Each rule is a pure function
`check(root_node, source_bytes, path) -> list[Diagnostic]` defined in one of the
rule-family modules (honest_code_rules, honest_type_rules, integration_rules) and
registered in `_ALL_CHECKS`; `check_source` parses once, short-circuits on a syntax
error (HC-SYN), then runs every registered rule. New rules are added by writing the
function in its family module and appending it to the registry here — a row, not a branch.

This module also re-exports the shared helpers external tooling imports from
`honest_check.rules` so the public import surface is unchanged.
"""

from honest_check.diagnostics import (
    Diagnostic,
    diagnostic,
)
from honest_parse import (
    first_error_node,
    line_col,
    parse,
)
from honest_check.suppression import (
    build_suppressions,
    collect_directives,
    dead_directives,
    is_suppressed,
    unexplained_directives,
)
from honest_check._rule_helpers import (
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
from honest_check.js_rules import check_hc_p001_js, check_hc_p002_js, check_hc_p003_js, check_hc_p004_js, check_hc_p005_js, check_hc_p006_js, check_hc_p011_js, check_hc_p016_js
from honest_check.honest_code_rules import (
    check_hc_p001,
    check_hc_p002,
    check_hc_p003,
    check_hc_p004,
    check_hc_p005,
    check_hc_p006,
    check_hc_p007,
    check_hc_p010,
    check_hc_p011,
    check_hc_p016,
    check_hc_p018,
)
from honest_check.honest_type_rules import (
    check_hc001,
    check_hc002,
    check_hc003,
    check_hc004,
    check_hc005,
    check_hc006,
    check_hc007,
    check_hc008,
    check_hc009,
    check_hc010,
    check_hc011,
    check_hc_p013,
    check_hc_p014,
    check_hc_p017,
    check_state_machine_reachability,
    check_state_machine_vocab,
)
from honest_check.integration_rules import (
    check_hc_a001,
    check_hc_a002,
    check_hc_hf001,
    check_hc_hf002,
    check_hc_or001,
    check_hc_or003,
    check_hc_r001,
    check_hc_st001,
)

def check_hc_syn(root, source: bytes, path: str) -> list[Diagnostic]:
    """HC-SYN — source does not parse. Short-circuits all other rules."""
    if not root.has_error:
        return []
    node = first_error_node(root)
    line, col = line_col(node) if node is not None else (1, 1)
    return [
        diagnostic("HC-SYN", "error", path, line, col, "Source does not parse. Fix the syntax error at this location so the file can be parsed.")
    ]


_ALL_CHECKS = (
    check_hc001,
    check_hc002,
    check_hc003,
    check_hc004,
    check_hc005,
    check_hc006,
    check_hc007,
    check_hc008,
    check_hc010,
    check_hc_p010,
    check_hc_p013,
    check_hc_p014,
    check_hc009,
    check_hc011,
    check_hc_a001,
    check_hc_a002,
    check_hc_hf001,
    check_hc_hf002,
    check_hc_or001,
    check_hc_or003,
    check_hc_p017,
    check_hc_r001,
    check_state_machine_vocab,
    check_state_machine_reachability,
    check_hc_p001,
    check_hc_p002,
    check_hc_p003,
    check_hc_p004,
    check_hc_st001,
    check_hc_p005,
    check_hc_p006,
    check_hc_p007,
    check_hc_p011,
    check_hc_p016,
    check_hc_p018,
)


# JavaScript rule registry (section 5). The Honest Code principles are language-agnostic; their
# JavaScript form is implemented over tree-sitter-javascript nodes. The honest-type-specific rules
# do not apply to vanilla JavaScript, so this registry holds only the structural rules.
_JS_CHECKS = (check_hc_p001_js, check_hc_p002_js, check_hc_p003_js, check_hc_p004_js, check_hc_p005_js, check_hc_p006_js, check_hc_p011_js, check_hc_p016_js)


# Section 2.3 — the grammar a file is checked under, by extension. Anything else is Python.
_LANGUAGE_BY_EXTENSION = {".js": "javascript", ".mjs": "javascript", ".cjs": "javascript"}


_CHECKS_BY_LANGUAGE = {
    "python": _ALL_CHECKS,
    "javascript": _JS_CHECKS,
}


def language_for_path(path: str) -> str:
    """The grammar a path is checked under (section 2.3): JavaScript for .js/.mjs/.cjs, else Python. Pure."""
    for extension, language in _LANGUAGE_BY_EXTENSION.items():
        if path.endswith(extension):
            return language
    return "python"


# Rules with a conservative, provably-safe automatic fix (section 2.1 --fix, section 6.2 fixable).
# honest-check's rules flag structural dishonesty that requires a human to restructure the code — a
# class is not mechanically a set of pure functions, and auto-inserting a suppression would defeat the
# linter — so there is none. A future rule whose fix is unambiguously safe would be listed here.
FIXABLE_RULES: frozenset = frozenset()


def is_fixable(rule: str) -> bool:
    """Whether a rule has a conservative automatic fix (section 2.1, 6.2). Pure."""
    return rule in FIXABLE_RULES


def check_source(source: str, path: str) -> list[Diagnostic]:
    """Parse `source` in its path's language, run that language's rules, then apply suppressions
    (section 1, 5, 7)."""
    language = language_for_path(path)
    src_bytes = source.encode("utf-8")
    root = parse(src_bytes, language).root_node
    syntax = check_hc_syn(root, src_bytes, path)
    if syntax:
        return syntax

    raw: list[Diagnostic] = []
    for check in _CHECKS_BY_LANGUAGE[language]:
        raw.extend(check(root, src_bytes, path))

    max_line = root.end_point[0] + 1
    inline, ranges = build_suppressions(root, src_bytes, max_line)
    out: list[Diagnostic] = []
    hits: set[tuple[str, int]] = set()
    for d in raw:
        if is_suppressed(d["rule"], d["line"], inline, ranges):
            hits.add((d["rule"], d["line"]))
            out.append(
                diagnostic(
                    d["rule"],
                    "info",
                    d["path"],
                    d["line"],
                    d["col"],
                    f"{d['rule']} suppressed by directive.",
                )
            )
        else:
            out.append(d)
    directives = collect_directives(root, src_bytes)
    for line, col, rule in dead_directives(directives, ranges, frozenset(hits)):
        out.append(
            diagnostic(
                "HC-SUP001",
                "error",
                path,
                line,
                col,
                f"Suppression of {rule} matched no diagnostic. A dead directive silently "
                "covers whatever this file grows next — delete it. See honest-check-architecture.md §7.4.",
            )
        )
    for line, col in unexplained_directives(directives):
        out.append(
            diagnostic(
                "HC-SUP002",
                "error",
                path,
                line,
                col,
                "Suppression carries no reason. Write '# honest: disable RULE: why' so the "
                "next reader can judge it. See honest-check-architecture.md §7.4.",
            )
        )
    return out
