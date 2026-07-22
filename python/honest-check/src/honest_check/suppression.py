"""Inline / block / file-level rule suppression (section 7).

Honest Code keeps suppressions visible: a suppressed diagnostic is not dropped, it
is downgraded to `info` so it still appears in output and does not silently
accumulate (section 7.4). This module is pure — it reads `# honest:` comment
directives from the parsed tree and answers whether a rule is suppressed at a line.

Directive forms (sections 7.1-7.2). Every ignore and disable carries a reason, after a
colon; `enable` only closes a block, so it needs none:
    # honest: ignore HC-P001: reason              inline — the comment's line only
    # honest: disable HC-P001: reason             block / file — until a matching enable or EOF
    # honest: enable  HC-P001                     ends a disable block
    # honest: disable HC-P001, HC-P003: reason    multiple rules, comma- or space-separated

Two rules keep the suppression surface honest (section 7.4). HC-SUP001 fires on a
directive that suppresses nothing — a dead directive is indistinguishable from a live
one, so it silently covers whatever violation the file grows next. HC-SUP002 fires on a
directive with no reason. Neither rule can itself be suppressed; a directive naming one
is inert, and so reports as dead.
"""

from honest_parse import node_text, walk

_VERBS = frozenset({"ignore", "disable", "enable"})

UNSUPPRESSABLE = frozenset({"HC-SUP001", "HC-SUP002"})


def _parse_directive(comment_text: str):
    """Parse `# honest: VERB RULE[, RULE...][: reason]` (or the JavaScript `// honest:`
    form); return (verb, frozenset(rules), reason) or None."""
    body = comment_text.lstrip("#/").strip()
    if not body.startswith("honest:"):
        return None
    rest = body[len("honest:") :].strip()
    parts = rest.split(None, 1)
    if not parts or parts[0] not in _VERBS:
        return None
    rules: set[str] = set()
    reason = ""
    if len(parts) > 1:
        rule_text, _, reason_text = parts[1].partition(":")
        reason = reason_text.strip()
        for token in rule_text.replace(",", " ").split():
            rules.add(token)
    return parts[0], frozenset(rules), reason


def collect_directives(root, source: bytes):
    """Every `# honest:` directive as (line, col, verb, rules, reason), in source order."""
    directives = []
    for node in walk(root):
        if node.type != "comment":
            continue
        parsed = _parse_directive(node_text(node, source))
        if parsed is None:
            continue
        verb, rules, reason = parsed
        directives.append(
            (node.start_point[0] + 1, node.start_point[1] + 1, verb, rules, reason)
        )
    directives.sort(key=lambda directive: directive[0])
    return directives


def build_suppressions(root, source: bytes, max_line: int):
    """Compute (inline, ranges): inline {line: {rule}}, ranges {rule: [(start, end)]}."""
    inline: dict[int, set[str]] = {}
    ranges: dict[str, list[tuple[int, int]]] = {}
    open_disables: dict[str, int] = {}
    for line, _col, verb, rules, _reason in collect_directives(root, source):
        suppressible = rules - UNSUPPRESSABLE
        if verb == "ignore":
            inline.setdefault(line, set()).update(suppressible)
        if verb == "disable":
            for rule in suppressible:
                open_disables.setdefault(rule, line)
        if verb == "enable":
            for rule in suppressible:
                start = open_disables.pop(rule, None)
                if start is not None:
                    ranges.setdefault(rule, []).append((start, line))
    for rule, start in open_disables.items():
        ranges.setdefault(rule, []).append((start, max_line))
    return inline, ranges


def _ignore_is_live(rule: str, line: int, hits) -> bool:
    """An inline ignore is live when the rule fired on its own line."""
    return (rule, line) in hits


def _disable_is_live(rule: str, line: int, ranges, hits) -> bool:
    """A disable is live when the rule fired inside the range that this directive opened.
    A directive that opened no range — a redundant second disable, or one naming an
    unsuppressable rule — opened nothing, so it is dead."""
    for start, end in ranges.get(rule, ()):
        if start != line:
            continue
        return any(rule == hit_rule and start <= hit_line <= end for hit_rule, hit_line in hits)
    return False


_LIVENESS = {
    "ignore": lambda rule, line, ranges, hits: _ignore_is_live(rule, line, hits),
    "disable": _disable_is_live,
    "enable": lambda rule, line, ranges, hits: True,
}


def dead_directives(directives, ranges, hits):
    """Directives that suppressed nothing, as (line, col, rule) — HC-SUP001."""
    dead = []
    for line, col, verb, rules, _reason in directives:
        is_live = _LIVENESS[verb]
        for rule in sorted(rules):
            if not is_live(rule, line, ranges, hits):
                dead.append((line, col, rule))
    return dead


def unexplained_directives(directives):
    """Suppressing directives carrying no reason, as (line, col) — HC-SUP002."""
    return [
        (line, col)
        for line, col, verb, _rules, reason in directives
        if verb != "enable" and not reason
    ]


def is_suppressed(rule: str, line: int, inline, ranges) -> bool:
    """True if `rule` is suppressed at `line` by an inline ignore or a disable range."""
    if rule in inline.get(line, frozenset()):
        return True
    for start, end in ranges.get(rule, ()):
        if start <= line <= end:
            return True
    return False
