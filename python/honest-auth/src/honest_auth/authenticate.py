"""The boundary authentication flow (sections 1.1, 2.2-2.3, 2.5): recognise the token, resolve the actor.

`authenticate` gates a token through the provider's `actor_recognizer` — a malformed token is rejected
here, before `resolve_actor` — and otherwise delegates to the provider's `resolve_actor`, which returns
`ok(actor)` or `err(fault)`. `fault_status` turns a fault into its HTTP status via the provider's
`fault_mapping`, falling back to the framework defaults. honest-auth is pure; the provider's recognizer
and resolver are the injected I/O at the boundary.
"""

from honest_type import err, fault

# Framework default category -> HTTP status (section 2.5); a provider's fault_mapping overrides per category.
_DEFAULT_STATUS = {"unauthenticated": 401, "forbidden": 403, "conflict": 409, "client": 400, "server": 500}


def authenticate(provider, token):
    """Validate a token at the boundary (section 2.2-2.4): a missing credential (None or empty) is
    unauthenticated — no identity was presented — and never reaches the recognizer or resolver; a token
    that does not match the provider's `actor_recognizer` is rejected as a malformed (client) fault,
    before `resolve_actor`; otherwise the provider's `resolve_actor` resolves it to `ok(actor)` or
    `err(fault)`. Pure; the recognizer and resolver are the provider's injected boundary I/O."""
    if token is None or token == "":
        return err(fault("unauthenticated", "no credential was presented at the boundary", "unauthenticated"))
    if not provider["actor_recognizer"](token):
        return err(fault("malformed_token", "token does not match the provider's wire format", "client"))
    return provider["resolve_actor"](token)


def fault_status(provider, auth_fault):
    """The HTTP status a fault maps to (section 2.5): the provider's fault_mapping for the fault's category,
    else the framework default, else 500. Pure."""
    category = auth_fault["category"]
    return provider["fault_mapping"].get(category, _DEFAULT_STATUS.get(category, 500))
