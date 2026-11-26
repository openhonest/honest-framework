# scenario: build_message
# inherits: hd=python/honest-alerts/honest-alerts.hd::build_message -> feature=specs/features/honest-alerts.feature::build_message
"""Red test for the build_message scenario (honest-alerts.feature).

build_message assembles one immutable Message from its already-computed parts and validates
it, returning the Message or a Fault -- a pure constructor that reads no clock, random source
or database (honest-alerts.hd build_message, feature scenario build_message, spec section 6b).

The scenario fixes these validation faults, each a client Fault via alerts_fault, and the .hd
note and spec section 6b pin the exact code for each:
  - a message carrying NO message_version at all          -> code missing_message_version       / client
  - registered is NOTHING (message_type never registered) -> code unregistered_message_type     / client
  - message_version not a member of registered set        -> code message_version_not_registered / client
  - a termination whose fields do not match its condition -> code invalid_termination           / client
and names that a message_version in the registered closed set returns a Message carrying it,
never a Fault, and that build_message never raises and never substitutes a default version.

Cases are data; one pure probe feeds them to the real build_message and returns a list of failure
strings (empty when every case holds). NOTHING is Python None. Records are flat dicts, the
honest-type canonical record shape. A Fault is recognised by is_err True; each fault case pins the
exact code and category. Successful sends assert every Message field. A reply-required case asserts the supplied
flag and options without choosing the later-unit resume token.
"""

from honest_alerts import build_message


# --- shared, already-computed parts (the impure parts are passed in, per the scenario) ---

_RECIPIENT = {"type": "user", "id": "u-recipient", "tenant_id": None}
_SENDER = {"type": "user", "id": "u-sender", "tenant_id": None}
_MESSAGE_ID = "0192f000-0000-7000-8000-000000000001"  # UUID v7 shape, passed in from new_message_id
_SENT_AT = 1_700_000_000  # epoch seconds UTC, passed in from now
_PAYLOAD = {"amount": 100}

# A well-formed termination: condition ttl, ttl_seconds set, the other fields NOTHING.
_TERMINATION_OK = {
    "condition": "ttl",
    "ttl_seconds": 3600,
    "event_type": None,
    "event_filter": None,
}

# A malformed termination: condition ttl but ttl_seconds is NOTHING, so its fields do not
# match its condition (the ttl seconds the ttl condition requires are absent).
_TERMINATION_BAD = {
    "condition": "ttl",
    "ttl_seconds": None,
    "event_type": None,
    "event_filter": None,
}


def _opts(message_version, termination):
    """A closed SendOpts bag carrying exactly the nine declared keys; version and termination vary.

    Every field is explicit; absence is NOTHING (None), never a default kwarg.
    """
    return {
        "message_version": message_version,
        "subject_label_id": "label.subject",
        "body_label_id": None,
        "channel": None,
        "dom_surface": None,
        "dom_target": None,
        "reply_options": None,
        "termination": termination,
        "ack_scope": "actor",
    }


_REGISTERED = {"message_type": "approval.requested", "message_versions": ["v1", "v2"]}


def _given(message_version, registered, termination):
    """The full build_message input; every parameter stated in full, nothing defaulted."""
    return {
        "message_type": "approval.requested",
        "recipient": _RECIPIENT,
        "payload": _PAYLOAD,
        "opts": _opts(message_version, termination),
        "sender": _SENDER,
        "message_id": _MESSAGE_ID,
        "sent_at": _SENT_AT,
        "reply_required": False,
        "registered": registered,
    }


_EXPECTED_SEND = {
    "message_id": _MESSAGE_ID,
    "message_type": "approval.requested",
    "message_version": "v1",
    "sender": _SENDER,
    "recipient": _RECIPIENT,
    "channel": None,
    "subject_label_id": "label.subject",
    "body_label_id": None,
    "payload": _PAYLOAD,
    "dom_surface": None,
    "dom_target": None,
    "reply_required": False,
    "reply_options": None,
    "resume_token": None,
    "termination": _TERMINATION_OK,
    "ack_scope": "actor",
    "sent_at": _SENT_AT,
}
_RICH_OPTIONS = {
    "message_version": "v2",
    "subject_label_id": "approval.subject",
    "body_label_id": "approval.body",
    "channel": "dom",
    "dom_surface": "inline",
    "dom_target": "#approval-panel",
    "reply_options": [
        {"option_id": "approve", "label_id": "approval.approve", "style": "primary", "payload": {"approved": True}},
    ],
    "termination": {
        "condition": "event",
        "ttl_seconds": None,
        "event_type": "approval.completed",
        "event_filter": {"request_id": "req-7"},
    },
    "ack_scope": "session",
}
_EXPECTED_REPLY_FIELDS = {
    **_RICH_OPTIONS,
    "message_id": _MESSAGE_ID,
    "message_type": "approval.requested",
    "sender": _SENDER,
    "recipient": _RECIPIENT,
    "payload": _PAYLOAD,
    "reply_required": True,
    "sent_at": _SENT_AT,
}


# Each row: the input in full and the output it must produce.
#   {"message": <record>}       -> an exact unit-1 Message is returned.
#   {"fault": (code, category)} -> a Fault carrying exactly that code and category is returned.
_CASES = [
    # valid: a version in the registered closed set, well-formed termination -> a Message carrying it
    # (the literal, non-trivial case: a stub returning a bare Fault or None fails this row).
    {"given": _given("v1", _REGISTERED, _TERMINATION_OK),
     "expect": {"message": _EXPECTED_SEND}},
    {
        "given": {
            **_given("v2", _REGISTERED, _TERMINATION_OK),
            "opts": _RICH_OPTIONS,
            "reply_required": True,
        },
        "expect": {"reply_fields": _EXPECTED_REPLY_FIELDS},
    },

    # a message carrying NO message_version at all (NOTHING) -> missing_message_version / client
    {"given": _given(None, _REGISTERED, _TERMINATION_OK),
     "expect": {"fault": ("missing_message_version", "client")}},

    # registered is NOTHING: the message_type was never registered -> unregistered_message_type / client
    {"given": _given("v1", None, _TERMINATION_OK),
     "expect": {"fault": ("unregistered_message_type", "client")}},

    # message_version carried but outside the registered closed set -> message_version_not_registered / client
    # (no default substituted; the registered record is the only authority)
    {"given": _given("v9", _REGISTERED, _TERMINATION_OK),
     "expect": {"fault": ("message_version_not_registered", "client")}},

    # a termination whose fields do not match its condition -> invalid_termination / client
    {"given": _given("v1", _REGISTERED, _TERMINATION_BAD),
     "expect": {"fault": ("invalid_termination", "client")}},
]


def _is_fault(got):
    return isinstance(got, dict) and got.get("is_err") is True


def probe_build_message():
    """A message_version in the registered closed set with a well-formed termination yields a
    Message carrying that version; a missing message_version yields missing_message_version, a
    NOTHING registered yields unregistered_message_type, an out-of-set version yields
    message_version_not_registered, and a termination whose fields do not match its condition
    yields invalid_termination -- each a client Fault via alerts_fault; build_message never raises."""
    bad = []
    for case in _CASES:
        given = case["given"]
        expect = case["expect"]
        try:
            got = build_message(**given)
        except Exception as exc:  # the scenario says it never raises
            bad.append(
                f"build_message raised {type(exc).__name__}: {exc} for "
                f"version={given['opts']['message_version']!r}, "
                f"registered={given['registered']!r}, "
                f"termination.ttl_seconds={given['opts']['termination']['ttl_seconds']!r}"
            )
            continue

        if "message" in expect:
            if got != expect["message"]:
                bad.append(f"build_message returned {got!r}, expected {expect['message']!r}")
        elif "reply_fields" in expect:
            if not isinstance(got, dict):
                bad.append(f"build_message returned {got!r}, expected a Message record")
                continue
            copied = {key: value for key, value in got.items() if key != "resume_token"}
            if copied != expect["reply_fields"]:
                bad.append(f"build_message returned reply fields {copied!r}, expected {expect['reply_fields']!r}")
        else:  # a fault case: pin the exact code and category
            want_code, want_category = expect["fault"]
            if not _is_fault(got):
                bad.append(
                    f"build_message returned {got!r} for version "
                    f"{given['opts']['message_version']!r}, registered={given['registered']!r}, "
                    f"expected a client Fault code {want_code!r}"
                )
                continue
            if got.get("code") != want_code:
                bad.append(
                    f"build_message Fault.code={got.get('code')!r}, expected {want_code!r} "
                    f"(version={given['opts']['message_version']!r}, "
                    f"registered={given['registered']!r}, "
                    f"termination.ttl_seconds={given['opts']['termination']['ttl_seconds']!r})"
                )
            if got.get("category") != want_category:
                bad.append(
                    f"build_message Fault.category={got.get('category')!r}, expected "
                    f"{want_category!r} for code {want_code!r}"
                )
    return bad


if __name__ == "__main__":
    import sys
    failures = probe_build_message()
    if failures:
        print(f"RED: {len(failures)} failure(s)")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("GREEN: build_message holds for every case")
