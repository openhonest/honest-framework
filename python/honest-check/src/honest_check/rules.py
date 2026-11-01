"""The rule catalogue, as data (honest-check.hd: the RuleId catalogue).

A rule is data the check_source core runs, not a separately declared function
of this module (P16: the table of rules is read by the pure core). Rules live
in a table keyed by the language honest-parse detected, so adding a language's
rule set is adding a row, never branching control flow. check_source reads this
table by the detected language, guarding the read with an explicit no-match row.

This run builds exactly one rule, HC-P003 (a class declaration), for exactly one
language, Python. The remaining forty-eight catalogue rules and the other
languages' rule sets are a tracked follow-on (bead honest-framework-4gv); they
are named as gaps, not stubbed to fake a pass.
"""

from honest_parse import line_col, walk

from honest_check.types import Diagnostic

# Each language's class-declaration node has its own tree-sitter type. This run
# carries Python only; the other languages' node types arrive with the follow-on
# rule sets.
_CLASS_NODE_TYPE_BY_LANGUAGE = {
    "python": "class_definition",
}


def _class_diagnostic(node, source_lines: list[str], path: str) -> Diagnostic:
    """One HC-P003 finding for one class-declaration node."""
    line, col = line_col(node)
    context = source_lines[line - 1] if 0 <= line - 1 < len(source_lines) else ""
    return Diagnostic(
        rule_id="HC-P003",
        severity="error",
        message=(
            "class declaration is dishonest: a data record is a TypedDict and "
            "behaviour is a pure function, so there is no class to hold state "
            "(HC-P003)"
        ),
        source_location=f"{path}:{line}:{col}",
        context=context,
        fixable=False,
    )


def check_hc_p003(root, language: str, source: str, path: str) -> list[Diagnostic]:
    """HC-P003: a class declaration. One Diagnostic per class node in the tree.

    The class-node type is looked up from the per-language table by subscript,
    guarded by the no-match row: a language the table does not carry has no
    built HC-P003 node type this run, so the rule produces no findings for it
    (gap honest-framework-4gv), rather than reading the Python node type against
    another language's tree.
    """
    if language not in _CLASS_NODE_TYPE_BY_LANGUAGE:
        return []
    node_type = _CLASS_NODE_TYPE_BY_LANGUAGE[language]
    source_lines = source.splitlines()
    return [
        _class_diagnostic(node, source_lines, path)
        for node in walk(root)
        if node.type == node_type
    ]


# The rule registry, keyed by language: the rules check_source runs over a file
# of that language. This run registers HC-P003 for Python.
_RULES_BY_LANGUAGE = {
    "python": (check_hc_p003,),
}


def rules_for(language: str):
    """The built rules for a language, or () when none are built for it yet.

    The no-match row on the registry read: a recognized language with no built
    rule set this run produces no findings (the other languages' rules are the
    follow-on honest-framework-4gv), which is the honest current state, not a
    swallowed violation.
    """
    if language not in _RULES_BY_LANGUAGE:
        return ()
    return _RULES_BY_LANGUAGE[language]
