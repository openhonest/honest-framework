"""Honesty tests (section 4): purity, mutation isolation, idempotency.

These verify, at runtime, that links behave the way Honest Code requires. They are derived
entirely from @link declarations - the developer writes nothing. Each returns a finding
(data) on violation, or None when honest; findings are never raised. Links declared
boundary=True are exempt: I/O at a declared boundary is expected to differ across calls.

Pure: the checks run the given links and compare results; deep copies guard the inputs.
"""

import copy

from honest_type.chains import execute_chain, link_meta
from honest_type.vocabulary import unwrap_maybe

from honest_test.enumeration import enumerate_sets


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


def _to_slots(type_case, binding):
    """Re-key an enumerated {type: value} case to the slots a link receives (section 4.6)."""
    out = {}
    for type_name, value in type_case.items():
        slot = unwrap_maybe(binding[type_name]) if binding and type_name in binding else type_name
        out[slot] = value
    return out


def enumerate_test_cases(vocab, binding):
    """Test manifests for a link from its accepts vocabulary (section 4.6): the Set product,
    keyed by slot."""
    return [_to_slots(case, binding) for case in enumerate_sets(vocab, binding)]


def test_chain_contracts(links):
    """Every valid output of link N must be accepted by link N+1 (section 4.6). Cases come
    from link N's declared accepts vocabulary; a pair where N has no accepts is skipped. Only
    a server fault from N+1 is a violation - a client fault is N+1 rightly rejecting bad data."""
    findings = []
    for index in range(len(links) - 1):
        producer, consumer = links[index], links[index + 1]
        meta = link_meta(producer)
        accepts = meta.get("accepts")
        if accepts is None:
            continue
        for test_manifest in enumerate_test_cases(accepts, meta.get("binds")):
            result = producer(test_manifest)
            if "ok" not in result:
                continue
            downstream = consumer(result["ok"])
            if "err" in downstream and downstream["err"].get("category") == "server":
                findings.append(
                    _finding("chain_contract", _name(consumer),
                             f"Rejected valid output from '{_name(producer)}'")
                )
    return findings
