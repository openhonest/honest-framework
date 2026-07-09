"""Auth0 provider TEMPLATE (adopter scaffold — outside the framework gate).

This is not a shipped provider. It is a starting point you copy into your own application and complete.
The framework ships no default provider (spec section 3.2); a weak default is a false sense of security.

`resolve_actor` FAILS CLOSED — it denies every request until you wire the JWKS verification below. That is
the safe, truthful state for an unconfigured provider: it authenticates nobody, and it will not pass
`authentication_honesty` until it is real (which is exactly the signal that you are not done).

Auth0 issues RS256 JWTs. To wire this template:
  1. Fetch and cache the tenant JWKS at  https://{domain}/.well-known/jwks.json  (confirm the current
     path in the Auth0 docs for your tenant/region).
  2. Verify the token signature against the key whose `kid` matches the JWT header.
  3. Check  iss == "https://{domain}/",  aud == audience  (your API identifier),  and exp is not past.
  4. Return  ok({"id": claims["sub"], ...})  on success.
"""

import re

from honest_type import err, fault, ok  # noqa: F401  (ok is used once resolve_actor is wired)

# A JWT on the wire: three dot-separated base64url segments (header.payload.signature).
_JWT = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")


def _is_jwt(token):
    return isinstance(token, str) and bool(_JWT.match(token))


def auth0_provider(domain, audience):
    """Build an Auth0 AuthProvider TEMPLATE. `domain` is your tenant host (e.g. acme.us.auth0.com);
    `audience` is your API identifier (the expected `aud` claim). Fill in `resolve` before use."""

    def resolve(token):
        # TEMPLATE — fail closed until wired. Verify the JWT against
        #   https://{domain}/.well-known/jwks.json  and check iss/aud/exp, then:
        #     return ok({"id": claims["sub"], "email": claims.get("email")})
        return err(fault("unauthenticated", "auth0 provider is a template and is not wired yet", "unauthenticated"))

    def test_tokens(class_name, context):
        # TEMPLATE — once resolve is wired, mint a real token per class from an Auth0 test tenant
        # (valid / revoked / expired / malformed / missing / forged). Missing is always None.
        return {"missing": None}.get(class_name)

    return {
        "name": "auth0",
        "actor_recognizer": _is_jwt,
        "resolve_actor": resolve,
        "test_token_generator": test_tokens,
        "fault_mapping": {"unauthenticated": 401, "forbidden": 403, "conflict": 409},
    }
