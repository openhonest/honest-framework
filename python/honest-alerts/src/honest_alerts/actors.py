"""The actor identity model (section 2).

An actor is anything that can send or receive a message. There is no actor registry: actors are named
in routing records and messages by an ActorRef of {type, id?, tenant_id?}. The declared types fall in
four groups — human, process, system, and interface — but no behaviour dispatches on the group, so the
vocabulary is the flat set of valid types. validate_actor_ref is the boundary check that a reference
names a declared type; id and tenant_id are optional and unconstrained here (resolution is the
supervisor's job, not this schema's).
"""

from honest_type import err, fault, ok

ACTOR_TYPES = frozenset(
    {
        # human
        "user", "role", "tenant", "admin", "anonymous",
        # process
        "chain", "state_machine", "job", "projection",
        # system
        "framework", "auth", "webhook_inbound",
        # interface
        "dom", "email", "sms", "webhook_outbound", "slack", "teams",
    }
)


def validate_actor_ref(ref):
    """An ActorRef names a declared actor type (section 2.1, 2.2). Returns ok(ref) or a client fault.
    Pure. id and tenant_id are optional and not constrained here."""
    if ref.get("type") not in ACTOR_TYPES:
        return err(fault("invalid_actor_type", f"'{ref.get('type')}' is not a declared actor type", "client", detail=ref.get("type")))
    return ok(ref)
