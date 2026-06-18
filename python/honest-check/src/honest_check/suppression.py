"""Inline / block / file-level rule suppression (section 7).

Honest Code keeps suppressions visible: a suppressed diagnostic is not dropped, it
is downgraded to `info` so it still appears in output and does not silently
accumulate (section 7.4). This module is pure — it reads `# honest:` comment
directives from the parsed tree and answers whether a rule is suppressed at a line.

Directive forms (sections 7.1-7.2):
    # honest: ignore HC-P001              inline — the comment's line only
    # honest: disable HC-P001             block / file — until a matching enable or EOF
    # honest: enable  HC-P001             ends a disable block
    # honest: disable HC-P001, HC-P003    multiple rules, comma- or space-separated
"""

from honest_check.parse import node_text, walk

_VERBS = frozenset({"ignore", "disable", "enable"})


def _parse_directive(comment_text: str):
    """Parse `# honest: VERB RULE[, RULE...]`; return (verb, frozenset(rules)) or None."""
    body = comment_text.lstrip("#").strip()
    if not body.startswith("honest:"):
        return None
    rest = body[len("honest:") :].strip()
    parts = rest.split(None, 1)
    if not parts or parts[0] not in _VERBS:
        return None
    rules: set[str] = set()
    if len(parts) > 1:
        for token in parts[1].replace(",", " ").split():
            rules.add(token)
    return parts[0], frozenset(rules)


def _collect_directives(root, source: bytes):
    """Every `# honest:` directive as (line, verb, rules), in source order."""
    directives = []
    for node in walk(root):
        if node.type != "comment":
            continue
        parsed = _parse_directive(node_text(node, source))
        if parsed is None:
            continue
        verb, rules = parsed
        directives.append((node.start_point[0] + 1, verb, rules))
    directives.sort(key=lambda directive: directive[0])
    return directives


def build_suppressions(root, source: bytes, max_line: int):
    """Compute (inline, ranges): inline {line: {rule}}, ranges {rule: [(start, end)]}."""
    inline: dict[int, set[str]] = {}
    ranges: dict[str, list[tuple[int, int]]] = {}
    open_disables: dict[str, int] = {}
    for line, verb, rules in _collect_directives(root, source):
        if verb == "ignore":
            inline.setdefault(line, set()).update(rules)
        if verb == "disable":
            for rule in rules:
                open_disables.setdefault(rule, line)
        if verb == "enable":
            for rule in rules:
                start = open_disables.pop(rule, None)
                if start is not None:
                    ranges.setdefault(rule, []).append((start, line))
    for rule, start in open_disables.items():
        ranges.setdefault(rule, []).append((start, max_line))
    return inline, ranges


def is_suppressed(rule: str, line: int, inline, ranges) -> bool:
    """True if `rule` is suppressed at `line` by an inline ignore or a disable range."""
    if rule in inline.get(line, frozenset()):
        return True
    for start, end in ranges.get(rule, ()):
        if start <= line <= end:
            return True
    return False
