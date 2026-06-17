"""The classification runner (honest-test spec §3.1, §3.6).

Auto-generated classification tests: run honest-type's classify() on a
vocabulary's own declaration. Every Set member must classify to its type
(accepted); every adversarial neighbor that is not itself a member must be
rejected. Failures are returned as data, not raised — the developer writes no
test code; the vocabulary IS the specification.
"""
from __future__ import annotations

from honest_type import classify_token

from honest_test.generate import adversarial_neighbors


def _set_recognizers(vocabulary: dict):
    """(type_name, kind, members) for each Set/insensitive base type.

    Recognizers are honest-type's runtime dict shape ({"kind", "members"})."""
    for name, recognizer in vocabulary.get("base_types", {}).items():
        kind = recognizer.get("kind")
        members = recognizer.get("members")
        if kind in ("set", "insensitive") and members:
            yield name, kind, members


def _all_members(vocabulary: dict) -> set:
    members: set = set()
    for _name, _kind, payload in _set_recognizers(vocabulary):
        members |= set(payload)
    return members


def _is_ticket(result) -> bool:
    return isinstance(result, dict) and "type" in result and "reason" not in result and "code" not in result


def classification_suite(vocabulary: dict) -> list:
    """Every Set member must classify to its own type. Returns failures."""
    failures = []
    for name, _kind, members in _set_recognizers(vocabulary):
        for member in sorted(members):
            result = classify_token(member, vocabulary)
            if not _is_ticket(result):
                reason = result.get("reason") or result.get("code") or "not-classified"
                failures.append({"kind": "not_classified", "type": name,
                                 "value": member, "detail": reason})
            elif result["type"] != name:
                failures.append({"kind": "wrong_type", "type": name,
                                 "value": member, "detail": result["type"]})
    return failures


def adversarial_suite(vocabulary: dict) -> list:
    """Every adversarial neighbor of a Set member (that is not itself a member)
    must be rejected. An accepted neighbor is an overlap / case / normalization
    / encoding bug. Returns failures."""
    failures = []
    members = _all_members(vocabulary)
    for name, kind, payload in _set_recognizers(vocabulary):
        if kind != "set":
            continue   # insensitive deliberately accepts case variants
        for member in sorted(payload):
            for neighbor in adversarial_neighbors(member):
                if neighbor in members:
                    continue   # the neighbor is itself a valid member
                if _is_ticket(classify_token(neighbor, vocabulary)):
                    failures.append({"kind": "accepted_neighbor", "type": name,
                                     "value": member, "neighbor": neighbor})
    return failures


def run_vocabulary(vocabulary: dict) -> dict:
    """Full auto-generated classification report for a vocabulary."""
    classification = classification_suite(vocabulary)
    adversarial = adversarial_suite(vocabulary)
    return {
        "classification_failures": classification,
        "adversarial_failures": adversarial,
        "passed": not classification and not adversarial,
    }
