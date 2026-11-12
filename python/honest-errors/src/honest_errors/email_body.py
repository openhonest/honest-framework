"""The email-body formatter (spec section 6). A pure rendering of a report to plain text: severity,
environment, time, type, message, location, truncated context and traceback. It performs no sending;
an email behavior in honest-alerts uses this body to build a Message. It lives here because the
rendering is a pure function of the ExceptionReport shape honest-errors owns.
"""

_CONTEXT_LIMIT = 500


def format_email_body(report):
    """Render a report into a plain-text email body (spec section 6)."""
    context_text = repr(report["context"])
    if len(context_text) > _CONTEXT_LIMIT:
        context_text = context_text[:_CONTEXT_LIMIT] + "... (truncated)"
    lines = [
        f"Severity:    {report['severity']}",
        f"Environment: {report['environment']}",
        f"Time:        {report['timestamp']}",
        f"Type:        {report['exception_type']}",
        f"Message:     {report['message']}",
        f"Location:    {report['file']}:{report['line']} in {report['function']}",
        "",
        f"Context:     {context_text}",
        "",
        "Traceback:",
        report["traceback"],
    ]
    return "\n".join(lines)
