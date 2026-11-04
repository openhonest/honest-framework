"""The law runner — honest-test's generative-verification import surface (spec section 4.10).

law states one property as data; verify_laws runs every law against every subject and returns
the run record. Both pure: verify_laws calls only the pure predicates the caller supplied.
"""


def law(identifier, statement, check):
    """State one property as data (spec section 4.10): a Law record of the identifier, the
    plain-language statement, and the pure predicate it is proven by. Reads no world."""
    return {"identifier": identifier, "statement": statement, "check": check}


def verify_laws(laws, subjects):
    """Run every law against every subject and return the run record (spec section 4.10): passed
    counts the law-and-subject pairs that held, total the pairs checked, and one Violation per
    failed pair carries the law identifier, statement, subject name and the check's messages.
    Reads no world; each check is a pure predicate the caller supplied."""
    passed = 0
    total = 0
    violations = []
    for one_law in laws:
        for subject in subjects:
            total += 1
            messages = one_law["check"](subject["params"])
            if messages:
                violations.append({
                    "law": one_law["identifier"],
                    "statement": one_law["statement"],
                    "subject": subject["name"],
                    "messages": messages,
                })
            else:
                passed += 1
    return {"passed": passed, "total": total, "violations": violations}
