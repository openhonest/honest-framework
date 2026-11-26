"""Apply the declared suppression directives and report policy findings (§7)."""

from ._util import choose, pick
from .diagnostics import diagnostic

# ---- suppression (§7) -------------------------------------------------------


# inherits: hd=python/honest-check/honest-check.hd::_is_directive -> feature=specs/features/honest-check.feature::_is_directive recognizes the stripped honest prefix -> test=python/honest-check/conformance/probe_suppression_is_directive.py::probe_suppression_is_directive
# hd: _is_directive
def _is_directive(text):
    return text.strip().lstrip("#/").strip().startswith("honest:")


_REASONED_VERBS = {"ignore", "disable"}


# inherits: hd=python/honest-check/honest-check.hd::_directive_record -> feature=specs/features/honest-check.feature::_directive_record extracts recognized rules and reason presence -> test=python/honest-check/conformance/probe_suppression_directive_record.py::probe_suppression_directive_record
# hd: _directive_record
def _directive_record(comment):
    text = comment.text.decode("utf-8")
    match _is_directive(text):
        case False:
            return None
    body = text.strip().lstrip("#/").strip()[len("honest:"):].strip()
    head, _, reason = body.partition(":")
    verb, *rule_fields = head.split(maxsplit=1) or [""]
    names = " ".join(rule_fields).replace(",", " ").split()
    match verb in _REASONED_VERBS | {"enable"} and bool(names):
        case False:
            return None
    return {
        "line": comment.start_point[0] + 1,
        "node": comment,
        "verb": verb,
        "rules": set(names),
        "has_reason": bool(reason.strip()),
    }


# inherits: hd=python/honest-check/honest-check.hd::_directives -> feature=specs/features/honest-check.feature::_directives retains the ranges each recognized directive owns -> test=python/honest-check/conformance/probe_suppression_directives.py::probe_suppression_directives
# hd: _directives
def _directives(ctx):
    comments = filter(lambda n: n.type == "comment", ctx["nodes"])
    directives = filter(lambda directive: directive is not None, map(_directive_record, comments))
    scoped = []
    open_ranges = {}
    for directive in directives:
        line = directive["line"]
        owned = []
        for rule in sorted(directive["rules"]):
            match directive["verb"], rule in open_ranges:
                case "ignore", _:
                    owned.append({"rule": rule, "first_line": line, "through_line": line})
                case "disable", False:
                    opened = {"rule": rule, "first_line": line + 1, "through_line": None}
                    open_ranges[rule] = opened
                    owned.append(opened)
                case "enable", True:
                    closed = open_ranges.pop(rule)
                    closed["through_line"] = line - 1
        scoped.append({"directive": directive, "ranges": owned})
    return scoped


# inherits: hd=python/honest-check/honest-check.hd::_diag_line -> feature=specs/features/honest-check.feature::_diag_line reads the line from the right of a source location -> test=python/honest-check/conformance/probe_suppression_diag_line.py::probe_suppression_diag_line
# hd: _diag_line
def _diag_line(diag):
    parts = diag["source_location"].rsplit(":", 2)
    return pick(
        len(parts) == 3 and parts[1].isdigit(),
        lambda: int(parts[1]),
        lambda: None,
    )


# inherits: hd=python/honest-check/honest-check.hd::_matches -> feature=specs/features/honest-check.feature::_matches checks inclusive ranges and excludes policy findings -> test=python/honest-check/conformance/probe_suppression_matches.py::probe_suppression_matches
# hd: _matches
def _matches(directive, diag):
    line = _diag_line(diag)
    rule = diag["rule_id"]
    return line is not None and rule not in {"HC-SUP001", "HC-SUP002"} and any(
        rule == owned["rule"]
        and owned["first_line"] <= line
        and (owned["through_line"] is None or line <= owned["through_line"])
        for owned in directive["ranges"]
    )


# inherits: hd=python/honest-check/honest-check.hd::_resolve_one -> feature=specs/features/honest-check.feature::_resolve_one preserves findings while downgrading matching severity -> test=python/honest-check/conformance/probe_suppression_resolve_one.py::probe_suppression_resolve_one
# hd: _resolve_one
def _resolve_one(diag, directives):
    suppressed = any(_matches(d, diag) for d in directives)
    return choose(suppressed, {**diag, "severity": "info"}, diag)


# inherits: hd=python/honest-check/honest-check.hd::_suppression_findings -> feature=specs/features/honest-check.feature::_suppression_findings reports dead and missing reason findings in order -> test=python/honest-check/conformance/probe_suppression_suppression_findings.py::probe_suppression_suppression_findings
# hd: _suppression_findings
def _suppression_findings(ctx, directives, raw_diagnostics):
    out = []
    for scoped in filter(lambda scoped: scoped["directive"]["verb"] in _REASONED_VERBS, directives):
        directive = scoped["directive"]
        dead = not any(_matches(scoped, diag) for diag in raw_diagnostics)
        reasonless = not directive["has_reason"]
        out.extend(
            pick(dead, lambda: [diagnostic(ctx, "HC-SUP001", "error", "suppression directive matched no diagnostic (dead directive)", directive["node"])], lambda: [])
        )
        out.extend(
            pick(reasonless, lambda: [diagnostic(ctx, "HC-SUP002", "error", "suppression directive carries no reason", directive["node"])], lambda: [])
        )
    return out


# inherits: hd=python/honest-check/honest-check.hd::apply_suppression -> feature=specs/features/honest-check.feature::apply_suppression closes only the enabled rule in a mixed list -> test=python/honest-check/conformance/probe_apply_suppression_closes_named_rule.py::probe_apply_suppression_closes_named_rule
# inherits: hd=python/honest-check/honest-check.hd::apply_suppression -> feature=specs/features/honest-check.feature::apply_suppression reports redundant disables and blank reasons -> test=python/honest-check/conformance/probe_apply_suppression_reports_redundancy.py::probe_apply_suppression_reports_redundancy
# inherits: hd=python/honest-check/honest-check.hd::apply_suppression -> feature=specs/features/honest-check.feature::apply_suppression ignores unrecognized verbs and preserves policy findings -> test=python/honest-check/conformance/probe_apply_suppression_preserves_policy.py::probe_apply_suppression_preserves_policy
# hd: apply_suppression
def apply_suppression(ctx, raw_diagnostics):
    """Apply line-scoped directives and append unsuppressible policy findings."""
    directives = _directives(ctx)
    resolved = [_resolve_one(d, directives) for d in raw_diagnostics]
    return resolved + _suppression_findings(ctx, directives, raw_diagnostics)
