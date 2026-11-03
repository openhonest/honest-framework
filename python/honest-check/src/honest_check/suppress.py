"""honest-check suppression pass, split from core.py for L1.17 (section 7)."""

from honest_parse import line_col
from honest_check.constants import _SUPPRESSION_KEYWORDS
from honest_check.nodes import diagnostic


def apply_suppression(ctx, raw_diagnostics):
    """Apply inline/file suppression to the raw diagnostics (section 7): downgrade a suppressed
    finding to info, and flag a directive that suppressed nothing (HC-SUP001) or carries no reason
    (HC-SUP002). The directive parsers nest here; ctx carries nodes, source and path."""
    nodes = ctx["nodes"]
    source = ctx["source"]
    def parse_directive(comment_node):
        """The suppression directive a comment states, or None when the comment is not one
        (§7.1). A directive reads `honest: <verb> RULE[, RULE...][: reason]`: the verb is one
        of _SUPPRESSION_KEYWORDS, the rules before the first `:` are split on commas and
        spaces, and the reason is the text after that `:`. A comment whose first word is not a
        verb — an ordinary `# honest: profiled` note or any other comment — is not a
        directive."""
        raw = comment_node.text.decode("utf-8") if comment_node.text else ""
        body = raw.lstrip("#").strip()
        if not body.startswith("honest:"):
            return None
        rest = body[len("honest:") :].strip()
        head = rest.split(None, 1)
        if not head or head[0] not in _SUPPRESSION_KEYWORDS:
            return None
        remainder = head[1] if len(head) > 1 else ""
        rule_part, separator, reason_part = remainder.partition(":")
        line, _col = line_col(comment_node)
        return {
            "keyword": head[0],
            "rules": rule_part.replace(",", " ").split(),
            "has_reason": separator == ":" and reason_part.strip() != "",
            "line": line,
            "node": comment_node,
        }
    def suppression_directives():
        """Every suppression directive in the file, in source-line order (§7.1). A disable's
        range depends on the enable that follows it, so the order they are resolved in is the
        order they sit on the page, not the order the walk happens to yield comments."""
        found = [
            parse_directive(node) for node in nodes if node.type == "comment"
        ]
        return sorted(
            (directive for directive in found if directive is not None),
            key=lambda directive: directive["line"],
        )
    def suppression_scopes(directives):
        """The list of suppression scopes the directives open (§7.1, §7.4). An `ignore` opens
        a point scope covering only its own line. A `disable RULE` opens a range from its line
        to the matching `enable RULE` (exclusive), or to end of file when no `enable` closes
        it; a second `disable` of an already-open rule opens no range, so it stays dead. Each
        scope carries the index of the directive that owns it, which is how liveness is
        credited back for HC-SUP001."""
        line_count = source.count("\n") + 1
        scopes = []
        open_ranges = {}

        # The directive keyword picks how a directive opens a scope (§7.1), dispatched as data
        # rather than a branch on the keyword value: an ignore opens a point scope on its own
        # line; a disable opens a range unless the rule is already open; an enable closes an
        # open range. Each handler mutates the shared scopes and open_ranges in place.
        def open_ignore(directive, line, index):
            for rule in directive["rules"]:
                scopes.append({"rule": rule, "lo": line, "hi": line, "owner": index})

        def open_disable(directive, line, index):
            for rule in directive["rules"]:
                if rule not in open_ranges:
                    open_ranges[rule] = (line, index)

        def close_enable(directive, line, index):
            for rule in directive["rules"]:
                if rule in open_ranges:
                    lo, owner = open_ranges.pop(rule)
                    scopes.append({"rule": rule, "lo": lo, "hi": line - 1, "owner": owner})

        open_scope = {"ignore": open_ignore, "disable": open_disable, "enable": close_enable}
        for index, directive in enumerate(directives):
            open_scope[directive["keyword"]](directive, directive["line"], index)
        for rule, (lo, owner) in open_ranges.items():
            scopes.append({"rule": rule, "lo": lo, "hi": line_count, "owner": owner})
        return scopes
    def diagnostic_line(diag):
        """The 1-based line a diagnostic sits on, read from its 'path:line:col' location. Every
        diagnostic this core builds carries that shape — diagnostic(ctx) formats it and the HC-SYN
        path returns before this pass runs — so the line is always present. Scope matching
        compares it against a directive's line."""
        parts = diag["source_location"].rsplit(":", 2)
        return int(parts[1])
    """The final pass (§7.4): downgrade each raw diagnostic a directive scope covers to
    info — kept in the list, never dropped — then append HC-SUP001 for a directive that
    suppressed nothing and HC-SUP002 for an `ignore`/`disable` with no reason. The two meta
    findings are independent and both may fire on one directive. HC-SUP001 and HC-SUP002
    are themselves never suppressed: they are appended after the downgrade pass and no
    scope ever covers them, so a directive naming either suppresses nothing and HC-SUP001
    reports it dead."""
    directives = suppression_directives()
    scopes = suppression_scopes(directives)
    live_owners = set()
    adjusted = []
    for diag in raw_diagnostics:
        line = diagnostic_line(diag)
        covering = [
            scope
            for scope in scopes
            if scope["rule"] == diag["rule_id"]
            and scope["lo"] <= line <= scope["hi"]
        ]
        if not covering:
            adjusted.append(diag)
            continue
        for scope in covering:
            live_owners.add(scope["owner"])
        adjusted.append({**diag, "severity": "info"})
    for index, directive in enumerate(directives):
        if directive["keyword"] == "enable":
            continue
        if index not in live_owners:
            adjusted.append(
                diagnostic(ctx,
                    "HC-SUP001",
                    "error",
                    "Suppression directive suppressed nothing: no named rule fired in its "
                    "scope. Remove the directive, or correct the rule it names.",
                    directive["node"],
                )
            )
        if not directive["has_reason"]:
            adjusted.append(
                diagnostic(ctx,
                    "HC-SUP002",
                    "error",
                    "Suppression directive carries no reason. Add ': <why the violation "
                    "stands>' so the next reader can judge whether it still holds.",
                    directive["node"],
                )
            )
    return adjusted
