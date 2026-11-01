"""The pure core of the checker (honest-check.hd: check_source, role fn).

It takes one source unit already held in memory, parses it under the grammar
honest-parse detects from path's extension, runs the built rules over the parse
tree, and returns the findings as data. It never opens a file (read_source does
that), never executes the application code it inspects, and never modifies
anything. It raises nothing: a violation comes back as a Diagnostic.

honest-parse owns the extension-to-grammar table and the parse, so there is no
second copy of that table here and no hand-rolled parser: check_source hands the
source and path to honest-parse and reads the tree it returns.

Scope of this run: the built rule is HC-P003 for Python (see rules.py). The full
RuleId catalogue and the §3.3/§3.4 declaration-graph extraction are a tracked
follow-on (bead honest-framework-4gv). The rules here read the parse tree
directly; reading a resolved declaration graph arrives with that follow-on.
"""

from honest_parse import language_of, parse_source

from honest_check.rules import rules_for
from honest_check.types import Diagnostic, RuleConfig


def _syntax_diagnostic(err: dict, path: str) -> Diagnostic:
    """HC-SYN: the source does not parse under its grammar, which gates every
    other rule. Emitted rather than returning [] so an unparseable file is never
    reported clean (no silent failure). The exact HC-SYN Diagnostic the
    conformance suite pins is part of the follow-on (honest-framework-4gv); this
    carries honest-parse's own error detail."""
    detail = err.get("detail", {})
    line = detail.get("line")
    col = detail.get("col")
    location = f"{path}:{line}:{col}" if line is not None and col is not None else path
    return Diagnostic(
        rule_id="HC-SYN",
        severity="error",
        message=err.get("message", f"{path} does not parse"),
        source_location=location,
        context="",
        fixable=False,
    )


def check_source(source: str, path: str, rule_config: RuleConfig) -> list[Diagnostic]:
    """Parse source under path's grammar, run the built rules, return findings."""
    language = language_of(path)
    if "ok" not in language:
        # An extension honest-parse cannot place. Discovery filters these out
        # before check_source runs (per the declaration), so this is unreached
        # in a normal run; report it as HC-SYN rather than silently returning [].
        return [_syntax_diagnostic(language["err"], path)]
    parsed = parse_source(source.encode("utf-8"), path)
    if "err" in parsed:
        return [_syntax_diagnostic(parsed["err"], path)]
    root = parsed["ok"].root_node
    findings: list[Diagnostic] = []
    for rule in rules_for(language["ok"]):
        findings.extend(rule(root, language["ok"], source, path))
    return findings
