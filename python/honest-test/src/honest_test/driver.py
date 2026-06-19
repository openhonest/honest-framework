"""Discovery driver (section 1): find a module's declared honest-framework objects and run
the generated tests against them.

This is what turns honest-test from a kit of checkers into a runnable verifier. Point it at
a module that declares state machines and links, and the suite is generated and run. discover
and verify take an already-imported module and introspect it (duck-typed, no isinstance); the
import itself is the caller's boundary. Findings are data; an empty list means honest.

Chains are not yet discovered (a chain is a closure, not introspectable by shape); links and
state machines are.
"""

import copy

from honest_type.chains import link_meta

from honest_test.honesty import detect_mutation, enumerate_test_cases, verify_purity
from honest_test.statemachine import (
    test_adversarial_transitions,
    test_invalid_transitions,
    test_valid_transitions,
)

_MACHINE_KEYS = frozenset({"states", "events", "transitions", "initial"})
_LINK_CHECKS = (verify_purity, detect_mutation)
_MACHINE_CHECKS = (test_valid_transitions, test_invalid_transitions, test_adversarial_transitions)


def _is_state_machine(obj):
    return hasattr(obj, "keys") and _MACHINE_KEYS <= set(obj.keys())


def _is_link(obj):
    return callable(obj) and hasattr(obj, "__honest_link__")


def discover(module):
    """The honest-framework objects a module declares: its links and state machines."""
    links = []
    machines = []
    for obj in vars(module).values():
        if _is_link(obj):
            links.append(obj)
        elif _is_state_machine(obj):
            machines.append(obj)
    return {"links": links, "machines": machines}


def _check_link(link):
    """Run the link honesty checks over the cases generated from its accepts vocabulary (a
    link with no accepts is exercised on the empty manifest). Each check gets a fresh copy."""
    meta = link_meta(link)
    accepts = meta.get("accepts")
    manifests = [{}]
    if accepts:
        manifests = enumerate_test_cases(accepts, meta.get("binds"))
    findings = []
    for manifest in manifests:
        for check in _LINK_CHECKS:
            finding = check(link, copy.deepcopy(manifest))
            if finding is not None:
                findings.append(finding)
    return findings


def verify(module):
    """Discover and run every applicable generated test on a module; return all findings
    (section 1). An empty list means the module's declared objects are honest."""
    found = discover(module)
    findings = []
    for machine in found["machines"]:
        for check in _MACHINE_CHECKS:
            findings.extend(check(machine))
    for link in found["links"]:
        findings.extend(_check_link(link))
    return findings
