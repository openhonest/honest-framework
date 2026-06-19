"""Honesty tests (section 4): purity, mutation isolation, idempotency.

These verify, at runtime, that links behave the way Honest Code requires. They are derived
entirely from @link declarations - the developer writes nothing. Each returns a finding
(data) on violation, or None when honest; findings are never raised. Links declared
boundary=True are exempt: I/O at a declared boundary is expected to differ across calls.

Pure: the checks run the given links and compare results; deep copies guard the inputs.
"""

import copy

from honest_type.chains import execute_chain, link_meta


def _finding(code, subject, message):
    return {"code": code, "subject": subject, "message": message}


def _is_boundary(link):
    return bool(link_meta(link).get("boundary"))


def _name(link):
    return link_meta(link).get("name") or getattr(link, "__name__", "<link>")


def verify_purity(link, manifest):
    """A pure link returns the same result for the same input, always (section 4.1). Boundary
    links are exempt."""
    if _is_boundary(link):
        return None
    if link(manifest) != link(manifest):
        return _finding("non_deterministic", _name(link), "Different results on identical input")
    return None


def detect_mutation(link, manifest):
    """A pure link must not modify its input manifest (section 4.2)."""
    before = copy.deepcopy(manifest)
    link(manifest)
    if before != manifest:
        return _finding("manifest_mutated", _name(link), "Link modified its input manifest")
    return None


def verify_idempotency(links, manifest):
    """The same chain run twice on the same manifest must produce the same result (section
    4.3). A chain containing any boundary link is exempt."""
    if any(_is_boundary(link) for link in links):
        return None
    if execute_chain(links, manifest) != execute_chain(links, copy.deepcopy(manifest)):
        return _finding("not_idempotent", "<chain>", "Different results on identical input")
    return None
