# scenario: _reserved_field faults a record other than Fault that declares is_err
# inherits: hd=python/honest-design/honest-design.hd::_reserved_field -> feature=python/honest-design/features/honest-design.feature::_reserved_field faults a record other than Fault that declares is_err
import re

_SOURCE = (
    'module example\n'
    '  type Result = { is_err: bool\n'
    ' value: int }\n'
)
_EXPECTED_CODE = "reserved_field"
_MESSAGE_FACTS = {
    "the reserved field and its owner": (
        r"\bis_err\b",
        r"\b(?:only|reserved|exclusive(?:ly)?|belongs?)\b",
        r"\bfault\b",
    ),
    "the corrective action": (
        (
            r"\b(?:remove|delete|drop|rename)\w*\b"
            r"|\b(?:name|give)\b.*\b(?:new|other|another|different|distinct|unique|else|owns?)\b"
        ),
        r"\b(?:field|is_err)\b",
    ),
    "the distinction between success and fault": (
        r"\b(?:success\w*|value|ok)\b",
        r"\b(?:fault|error)\b",
        r"\b(?:\w*distinguish\w*|separat\w*|discriminat\w*|tell\b.*\bapart|\bmark\b.*\btells?)\b",
    ),
}


def probe_reserved_field_foreign_record():
    from honest_design import read_hd
    from honest_design.validator import _reserved_field

    module = read_hd(_SOURCE)["ok"]["modules"][0]
    faults = _reserved_field(module)

    codes = [fault["code"] for fault in faults]
    if codes != [_EXPECTED_CODE]:
        return [f"Expected one {_EXPECTED_CODE} diagnostic, received {codes!r}"]
    message = faults[0]["message"].casefold()
    clauses = re.split(r"[.!?;:\n]", message)
    return [
        f"Diagnostic does not explain {fact}: {faults[0]['message']!r}"
        for fact, concepts in _MESSAGE_FACTS.items()
        if not any(all(re.search(pattern, clause) for pattern in concepts) for clause in clauses)
    ]
