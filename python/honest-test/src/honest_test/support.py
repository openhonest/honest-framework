"""Shared record constructors for honest-test (private helpers).

A Finding is honest-test's one result record (honest-test.hd, type Finding): a grade, a
code, a human message and a location. A Fault is the module's own failure record
(honest-test.hd, type Fault): a problem and a remedy. Both are plain data, returned, never
raised in the interior.
"""


def _finding(kind, code, message, location=""):
    """One Finding record (honest-test.hd): kind is the grade, code the closed condition,
    message the human sentence, location file:line:col or the empty string."""
    return {"kind": kind, "code": code, "message": message, "location": location}


def _fault(problem, remedy):
    """One honest-test Fault record (honest-test.hd, type Fault): what went wrong and what to
    do instead, the two fields that make it self-explaining."""
    return {"problem": problem, "remedy": remedy}


def _is_fault(value):
    """True when a value is a honest-test Fault (problem + remedy), not a Result or list."""
    return hasattr(value, "get") and "problem" in value and "remedy" in value
