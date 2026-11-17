"""The boundary flow and the status mapping (honest-auth-architecture.md §2.2, §2.3, §2.5).
authenticate runs the provider's injected recognizer and resolver and returns the resolved Actor or a
typed failure; fault_status turns a Fault into the HTTP status the boundary returns. honest-auth
performs no I/O here: the recognizer and resolve_actor are injected provider callables, and the real
reads live inside resolve_actor at the application's request boundary. Pure composition over them.
"""

from honest_auth._util import _pick
from honest_auth.types import MALFORMED_CODE, auth_fault


def authenticate(provider, token):
    """Run the provider's recognizer and resolver and return the resolved Actor or a typed failure
    (§2.3, §4.7). It first runs the injected actor_recognizer on the token; a token that fails it is
    malformed and authenticate returns an auth_fault at once, before resolve_actor, with category
    unauthenticated and code malformed_token (§2.2, §2.4). A token that passes is handed to the
    injected resolve_actor, whose Actor or Fault is returned unchanged (§2.3). Pure composition over
    the injected callables."""
    return _pick(
        bool(provider["actor_recognizer"](token)),
        lambda: provider["resolve_actor"](token),
        lambda: auth_fault(
            "unauthenticated",
            MALFORMED_CODE,
            "token does not match the provider's actor_recognizer; it is rejected before resolution",
            {"token_class": "malformed"},
        ),
    )


def fault_status(provider, fault):
    """Translate an AuthFault into the HTTP response status the boundary returns, by looking the
    fault's category up in the provider's fault_mapping (§2.5). unauthenticated maps to 401, forbidden
    to 403, conflict to 409, plus any category the provider added. Pure over the injected mapping;
    §2.5 guarantees unauthenticated is always mapped, so the no-valid-identity categories resolve, and
    a category the provider returned but never mapped is a provider bug the bare read surfaces at
    once."""
    return provider["fault_mapping"][fault["category"]]
