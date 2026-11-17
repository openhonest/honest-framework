"""honest-utilities — the capability several modules share and none owns (honest-utilities-architecture.md).

Two capabilities, each entered by import and running from no flow of its own. The law runner (door
`verify_laws`) checks a caller's injected predicate across a bounded space of subjects and reports
failures as Violations, never faults. The environment-variable reader (door `read_env`) coerces named
variables to a caller-declared type, returns NOTHING for an absent optional, and returns one Fault
naming every missing-required or uncoercible variable together.

Fault is honest-type's shape across the seam: built with honest_type.fault, carried as a bare union
`X | Fault` recognized by shape — a record carrying a "code" — never raised and never wrapped in an
ok/err envelope. NOTHING is the explicit absence sentinel, the empty tuple, defined locally so this
foundation-layer module depends on nothing above honest-type.

If-free by construction (P01, P16). A branch is a bool key into a closed two-row table of thunks
(`pick`), or an open-key read guarded by its no-match row (`read_or`), so this file carries no `if`
statement, no conditional expression, and no comprehension if-clause.
"""

import os
import re
import uuid
from typing import Any, Callable, TypedDict

from honest_type import fault

# ---------------------------------------------------------------------------
# If-free control primitives (P01, P16), mirroring honest-errors and honest-parse.
# ---------------------------------------------------------------------------

_TWO_ROW = {True: lambda when_true, when_false: when_true,
            False: lambda when_true, when_false: when_false}


def pick(flag, when_true, when_false):
    """Call and return when_true() when flag is truthy, else when_false(). Only the chosen arm runs."""
    return _TWO_ROW[bool(flag)](when_true, when_false)()


def read_or(table, key, default_thunk):
    """table[key] when key is a member, else default_thunk() — the open-key read guarded by its
    no-match row, never the silent default of table.get(key, default)."""
    return pick(key in table, lambda: table[key], default_thunk)


def _is_fault(value):
    """Recognize the Fault arm of a bare `X | Fault` union: a dict carrying a "code". A coerced scalar
    never is one. The isinstance guard short-circuits, so "code" is never tested against a non-dict."""
    return isinstance(value, dict) and "code" in value  # honest: ignore HC-P005: bare-union recognizer for the scalar|Fault seam — isinstance is the arm discriminant, and honest-type's "code"-in-value test would raise on a scalar coerced value


# ---------------------------------------------------------------------------
# The absence sentinel. An optional field holds a value or NOTHING.
# ---------------------------------------------------------------------------

NOTHING: Any = ()

# ---------------------------------------------------------------------------
# The closed target-type vocabulary (Appendix B).
# ---------------------------------------------------------------------------

TARGET_TYPES = frozenset({"str", "int", "bool", "float", "UUID", "key"})

# ---------------------------------------------------------------------------
# The data dictionary (Appendix A and B). Plain records; TypedDict, never classes.
# ---------------------------------------------------------------------------


class Law(TypedDict):
    identifier: str
    statement: str
    check: Callable


class Subject(TypedDict):
    name: str
    params: dict


class Violation(TypedDict):
    identifier: str
    statement: str
    subject: str
    messages: list


class LawRun(TypedDict):
    passed: int
    total: int
    violations: list


class EnvRequest(TypedDict):
    name: str
    type_name: str
    required: bool


class EnvValues(TypedDict):
    values: dict


class Fault(TypedDict):
    code: str
    message: str
    category: str
    detail: dict


# ===========================================================================
# Capability 1 — the law runner, an engine (Appendix A).
# ===========================================================================


def verify_laws(laws, subjects):
    """The law-runner door (Appendix A): hands the two lists to run_laws and returns the LawRun."""
    return run_laws(laws, subjects)


def run_laws(laws, subjects):
    """The law-runner orchestrator (Appendix A). Runs each law against each subject at run_check's
    boundary, builds one Violation per failed pair, and assembles the LawRun where passed plus the
    number of violations equals total."""
    pairs = [(one_law, subject) for one_law in laws for subject in subjects]
    results = [_run_pair(one_law, subject) for (one_law, subject) in pairs]
    violations = list(filter(lambda v: v is not NOTHING, results))
    total = len(pairs)
    return {"passed": total - len(violations), "total": total, "violations": violations}


def _run_pair(one_law, subject):
    """One law against one subject: a Violation when the check returns messages, else NOTHING."""
    messages = run_check(one_law["check"], subject["params"])
    return pick(
        len(messages) > 0,
        lambda: to_violation(one_law, subject, messages),
        lambda: NOTHING,
    )


def run_check(check, params):
    """The law engine's boundary (Appendix A): runs the caller's injected predicate — code this module
    did not write — on one subject's params and returns its messages, empty when the property holds."""
    return check(params)


def to_violation(one_law, subject, messages):
    """The pure half of the law engine (Appendix A): records one failed pair as a Violation."""
    return {
        "identifier": one_law["identifier"],
        "statement": one_law["statement"],
        "subject": subject["name"],
        "messages": messages,
    }


def law(identifier, statement, check):
    """The pure constructor a sibling imports to write its own generative conformance (Appendix A)."""
    return {"identifier": identifier, "statement": statement, "check": check}


# ===========================================================================
# Capability 2 — the environment-variable reader, a reader (Appendix B).
# ===========================================================================


def read_env(declarations):
    """The reader's door (Appendix B): hands the declarations to load_env and returns the EnvValues or
    the one aggregate Fault."""
    return load_env(declarations)


def load_env(declarations):
    """The reader's orchestrator (Appendix B): reads the environment once through read_raw_env, then
    hands the declarations and the raw map to resolve_env and returns its answer."""
    names = [declaration["name"] for declaration in declarations]
    raw = read_raw_env(names)
    return resolve_env(declarations, raw)


def read_raw_env(names):
    """The capability's boundary (Appendix B): the one place the process environment is touched. Maps
    each declared name to its raw string, or to NOTHING when the variable is absent."""
    return {name: read_or(os.environ, name, lambda: NOTHING) for name in names}


def resolve_env(declarations, raw):
    """Resolve the raw map against the declarations (Appendix B). Three cases per declaration: an absent
    required variable is a failure, an absent optional resolves to NOTHING, a present variable coerces
    through by_target_type. Every failure is collected into one Fault naming every failing variable
    together; a key variable's name may appear but never its value."""
    resolutions = [_resolve_one(declaration, raw) for declaration in declarations]
    failures = list(filter(lambda resolution: resolution["outcome"] == "fail", resolutions))
    return pick(
        len(failures) > 0,
        lambda: _aggregate_fault(failures),
        lambda: _env_values(resolutions),
    )


def _resolve_one(declaration, raw):
    """One declaration resolved against the raw map: a value resolution or a failure resolution."""
    rawval = raw[declaration["name"]]
    return pick(
        rawval is NOTHING,
        lambda: _resolve_absent(declaration),
        lambda: _resolve_present(declaration, rawval),
    )


def _resolve_absent(declaration):
    """An absent variable: a failure when required, NOTHING when optional."""
    return pick(
        declaration["required"],
        lambda: {"outcome": "fail", "name": declaration["name"], "reason": "missing required variable"},
        lambda: {"outcome": "value", "name": declaration["name"], "value": NOTHING},
    )


def _resolve_present(declaration, rawval):
    """A present variable: coerced to its declared type, or a failure when the coercer rejects it."""
    coerced = _coercer_for(declaration["type_name"])(rawval)
    return pick(
        _is_fault(coerced),
        lambda: {"outcome": "fail", "name": declaration["name"], "reason": "value will not coerce"},
        lambda: {"outcome": "value", "name": declaration["name"], "value": coerced},
    )


def _coercer_for(type_name):
    """Select the coercer for a target type (Appendix B), guarded by the no-match row. A word outside
    the six-row vocabulary can only be a construction bug, so the fallback is a coercer that faults."""
    return read_or(by_target_type, type_name, lambda: _unknown_target_type)


def _unknown_target_type(raw):
    """The no-match coercer: a self-describing server fault for a target type no row carries."""
    accepted = sorted(by_target_type)
    return fault(
        "unknown_target_type",
        f"target type matched no coercer; accepted types are {accepted}",
        "server",
        [],
        {"accepted": accepted},
    )


def _env_values(resolutions):
    """Assemble the EnvValues from value resolutions: each declared name to its coerced value or NOTHING."""
    return {"values": {resolution["name"]: resolution["value"] for resolution in resolutions}}


def _aggregate_fault(failures):
    """One Fault naming every failing variable together (Appendix B). Only names are reported, never
    values, so a key variable's secret never appears."""
    names = [failure["name"] for failure in failures]
    detail = [{"name": failure["name"], "reason": failure["reason"]} for failure in failures]
    return fault(
        "env_unresolved",
        "environment configuration failed for: " + ", ".join(names),
        "server",
        [],
        {"variables": detail},
    )


# ---------------------------------------------------------------------------
# The six coercers (Appendix B), one per by_target_type row. Each returns the
# coerced value or a Fault; none raises. Validation is a regex or a closed word
# table, so no coercer catches an exception.
# ---------------------------------------------------------------------------

_INT_RE = re.compile(r"[+-]?[0-9]+")
_FLOAT_RE = re.compile(r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

_BOOL_WORDS = {
    "true": True, "1": True, "yes": True, "on": True,
    "false": False, "0": False, "no": False, "off": False,
}


def _uncoercible(type_name, expected):
    """A coercion Fault that names the target type and what was expected, never the rejected value."""
    return fault(
        "uncoercible_value",
        f"value does not coerce to {type_name}; expected {expected}",
        "server",
        [],
        {"target_type": type_name, "expected": expected},
    )


def coerce_str(raw):
    """str (Appendix B): the raw string passes through unchanged. Never fails."""
    return raw


def coerce_int(raw):
    """int (Appendix B): the raw string parses as a whole number, else a Fault."""
    return pick(
        _INT_RE.fullmatch(raw) is not None,
        lambda: int(raw),
        lambda: _uncoercible("int", "a whole number"),
    )


def coerce_bool(raw):
    """bool (Appendix B): 'true'/'1'/'yes'/'on' read true and 'false'/'0'/'no'/'off' read false,
    case-insensitive; any other word is a Fault."""
    return read_or(_BOOL_WORDS, raw.lower(), lambda: _uncoercible("bool", "a boolean word"))


def coerce_float(raw):
    """float (Appendix B): the raw string parses as a number, else a Fault."""
    return pick(
        _FLOAT_RE.fullmatch(raw) is not None,
        lambda: float(raw),
        lambda: _uncoercible("float", "a number"),
    )


def coerce_uuid(raw):
    """UUID (Appendix B): the raw string parses as a UUID, else a Fault."""
    return pick(
        _UUID_RE.fullmatch(raw) is not None,
        lambda: uuid.UUID(raw),
        lambda: _uncoercible("UUID", "a UUID"),
    )


def coerce_key(raw):
    """key (Appendix B): a secret passes through as its string; its value never appears in a fault
    message or anywhere this module reports — only the variable's name does. Never fails."""
    return raw


# ---------------------------------------------------------------------------
# The coercer dispatch (Appendix B): the one place the six coercions are
# enumerated, one row per TargetType word.
# ---------------------------------------------------------------------------

by_target_type = {
    "str": coerce_str,
    "int": coerce_int,
    "bool": coerce_bool,
    "float": coerce_float,
    "UUID": coerce_uuid,
    "key": coerce_key,
}


__all__ = [
    "NOTHING",
    "law",
    "verify_laws",
    "read_env",
    "resolve_env",
    "coerce_str",
    "coerce_int",
    "coerce_bool",
    "coerce_float",
    "coerce_uuid",
    "coerce_key",
]
