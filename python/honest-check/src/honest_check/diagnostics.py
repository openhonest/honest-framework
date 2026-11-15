"""The one Diagnostic builder every rule calls, plus the closed auto-fix subset
(§3.4). A Diagnostic is data: a violation comes back as this record, never as an
exception."""

# NOTHING, the absence arm honest-check threads where a value may be absent.
NOTHING = None

# honest-check's closed auto-fix subset. Empty: the spec enumerates no mechanically
# fixable rule, so every finding's `fixable` is False (§3.4).
fixable_rules = frozenset()


def diagnostic(ctx, rule_id, severity, message, node):
    """Build one Diagnostic for a rule firing at a node: pass-through rule_id,
    severity and message; source_location as path:line:col over the context's source
    bytes; context the verbatim source line; fixable from the auto-fix subset."""
    row, column = node.start_point
    line = row + 1
    col = column + 1
    source_line = ctx["source"].decode("utf-8").splitlines()[row]
    return {
        "rule_id": rule_id,
        "severity": severity,
        "message": message,
        "source_location": f"{ctx['path']}:{line}:{col}",
        "context": source_line,
        "fixable": rule_id in fixable_rules,
    }


def file_diagnostic(path, rule_id, severity, message):
    """Build a file-level Diagnostic that carries no single line — the shape HC-SYN
    takes, since a file that does not parse has no node to point at (§2.3)."""
    return {
        "rule_id": rule_id,
        "severity": severity,
        "message": message,
        "source_location": path,
        "context": "",
        "fixable": rule_id in fixable_rules,
    }
