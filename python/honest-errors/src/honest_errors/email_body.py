"""The email-body formatter (architecture section 6).

A pure rendering of an ExceptionReport to plain text: severity, environment, time, type, message,
location, a truncated context and the traceback. It sends nothing; an email behavior in honest-alerts
uses the text to build a Message body. It lives here because the rendering is a pure function of the
ExceptionReport shape honest-errors owns.
"""

_CONTEXT_LIMIT = 500


def format_email_body(report):
    """Render an ExceptionReport to a plain-text email body (section 6). The context is truncated to a
    bounded length so one oversized context cannot produce an unbounded body."""
    context_text = str(report["context"])
    truncated_context = context_text[:_CONTEXT_LIMIT]
    lines = [
        f"Severity: {report['severity']}",
        f"Environment: {report['environment']}",
        f"Time: {report['timestamp']}",
        f"Type: {report['exception_type']}",
        f"Message: {report['message']}",
        f"Location: {report['file']}:{report['line']} in {report['function']}",
        f"Context: {truncated_context}",
        "Traceback:",
        report["traceback"],
    ]
    return "\n".join(lines)
