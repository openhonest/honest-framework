"""Law-driven conformance — the behavioural circle (conformance-suite spec).

A law is a universal property over a labelled subject. honest-test's generators
(enumerate_sets, adversarial_neighbours, ...) supply the bounded input space *inside* each
law's check, so the declaration is the test specification (section 3.1): the subject is the
module's own declaration, the generated inputs are exhaustive over its bounded vocabulary,
and the law is the assertion that holds across that space.

This module is the generic runner only. The module-specific laws (HT-* for honest-type,
HP-* for honest-persist, HC-* for honest-check) live in each module's conformance harness,
which supplies its own declarations as subjects. The runner stays free of any module
dependency, so there is no cycle: honest-test never imports the modules it verifies.

Violations are data, never exceptions: a check returns a list of human-readable failure
messages (empty means the law holds for that subject). The report is data too.
"""


def law(law_id, statement, check):
    """A conformance law: an id, its English statement, and check(subject) -> list[str].

    The check returns one message per violation it finds in the subject (empty list when the
    law holds). The check owns its input generation — it calls the generators over the
    subject's bounded vocabulary."""
    return {"id": law_id, "statement": statement, "check": check}


def verify_laws(laws, subjects):
    """Run every law over every (label, subject) pair.

    Returns a report: {passed, failed, total, violations} where each violation is
    {law, statement, subject, messages}. Pure given pure checks — the checks generate their
    own bounded inputs and return violation messages as data."""
    violations = []
    checks_run = 0
    for entry in laws:
        for label, subject in subjects:
            checks_run += 1
            messages = entry["check"](subject)
            if messages:
                violations.append(
                    {
                        "law": entry["id"],
                        "statement": entry["statement"],
                        "subject": label,
                        "messages": list(messages),
                    }
                )
    return {
        "passed": checks_run - len(violations),
        "failed": len(violations),
        "total": checks_run,
        "violations": violations,
    }
