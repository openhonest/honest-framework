"""Classification: find which recognizer (if any) matches a token.

`classify_token(text, vocab)` returns a Ticket on match, or a Rejection
when no recognizer accepts the input. Pure function.

HC-003 is enforced here: if more than one recognizer matches the same
token, we raise a value error (rejection with overlap code). A vocabulary
where two recognizers overlap is ill-formed by design.
"""
from __future__ import annotations

from honest_type.types import Rejection, Ticket, Vocabulary


def classify_token(text: str, vocab: Vocabulary) -> Ticket | Rejection:
    """Pure. Return a Ticket if exactly one recognizer matches, else a
    Rejection.
    """
    matches: list[str] = []
    tried: list[str] = []
    for name, recognizer in vocab["recognizers"].items():
        tried.append(name)
        if recognizer(text):
            matches.append(name)

    if len(matches) == 0:
        return emit_rejection(text, "unrecognized_shape", tried)
    if len(matches) > 1:
        return emit_rejection(
            text,
            f"recognizer_overlap:{','.join(matches)}",
            tried,
        )
    return Ticket(type=matches[0], value=text, slot="")


def emit_rejection(value: str, reason: str, attempted: list[str]) -> Rejection:
    """Pure constructor."""
    return Rejection(value=value, reason=reason, attempted=list(attempted))


# Alias used elsewhere in the framework.
classify = classify_token
