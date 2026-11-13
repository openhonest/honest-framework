"""The capture door and the handle_failure orchestrator (architecture section 7).

A failure enters through the capture boundary and leaves as one FailurePolicy. handle_failure holds the
normalize -> behaviors -> throttle -> render sequence; capture holds none of it, forwarding every
argument to the orchestrator. Neither touches a world of its own: environment, timestamp, config, state
and now are all handed in.
"""

from honest_errors.behaviors import behaviors_for
from honest_errors.classify import normalize_by_source, should_bypass_dedup
from honest_errors.email_body import format_email_body
from honest_errors.throttle import check_rate_limit, dedup_key


def handle_failure(source, payload, environment, timestamp, config, state, now):
    """Run the whole policy for one captured failure (section 7). source selects the normalizer through
    normalize_by_source; a source matching no normalizer returns an unknown_source Fault, and a malformed
    payload comes back as a Fault, each short-circuiting before any policy. An unknown environment returns
    its Fault before a FailurePolicy is built. Otherwise it reads the behaviors, throttles on the report's
    dedup key, and renders the email body only when the policy includes an email behavior and the send is
    warranted (the throttle says send, or a critical severity bypasses it). It assembles one FailurePolicy
    carrying the report, the behaviors, the decision, the next state and the email body."""
    if source not in normalize_by_source:
        accepted = sorted(normalize_by_source)
        return {
            "code": "unknown_source",
            "message": f"payload source {source!r} matched no normalizer; accepted sources are {accepted}",
        }
    report = normalize_by_source[source](payload, environment, timestamp)
    if "code" in report:
        return report
    behaviors = behaviors_for(environment)
    if "code" in behaviors:
        return behaviors
    outcome = check_rate_limit(dedup_key(report), config, state, now)
    decision = outcome["decision"]
    has_email_behavior = any(behavior["name"] == "email" for behavior in behaviors)
    warrants_email = has_email_behavior and (
        decision["should_send"] or should_bypass_dedup(report["severity"])
    )
    email_body = format_email_body(report) if warrants_email else ""
    return {
        "report": report,
        "behaviors": behaviors,
        "decision": decision,
        "next_state": outcome["next_state"],
        "email_body": email_body,
    }


def capture(source, payload, environment, timestamp, config, state, now):
    """The door the world enters through (section 7): a browser error hook or a server error boundary
    catches a failure and calls this. It transforms nothing; it forwards every argument to
    handle_failure and returns the FailurePolicy, or the Fault a malformed payload or unknown
    environment produced."""
    return handle_failure(source, payload, environment, timestamp, config, state, now)
