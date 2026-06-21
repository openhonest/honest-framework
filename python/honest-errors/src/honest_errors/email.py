"""The email-body formatter (section 6): a pure rendering of a report to plain text.

It performs no sending; an `email` behavior in honest-alerts uses it to build a message body. It
lives here, not in alerts, because the rendering is a pure function of the `ExceptionReport` shape
honest-errors owns. The context is truncated so a large attached context cannot bloat the body.
"""

_CONTEXT_LIMIT = 10


def format_email_body(report):
    """Render an ExceptionReport to a plain-text email body (section 6). Pure."""
    items = list(report.get("context", {}).items())[:_CONTEXT_LIMIT]
    rendered_context = ", ".join(f"{key}={value}" for key, value in items)
    return "\n".join(
        [
            f"Severity:    {report['severity']}",
            f"Environment: {report['environment']}",
            f"Time:        {report['timestamp']}",
            f"Type:        {report['exception_type']}",
            f"Message:     {report['message']}",
            f"Location:    {report['file']}:{report['line']} in {report['function']}",
            f"Context:     {rendered_context}",
            "",
            "Traceback:",
            report["traceback"],
        ]
    )
