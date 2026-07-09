"""Clerk provider TEMPLATE (adopter scaffold — outside the framework gate).

This is not a shipped provider. Copy it into your application and complete `resolve_actor`. The framework
ships no default provider (spec section 3.2). `resolve_actor` FAILS CLOSED until you wire it — an
unconfigured provider authenticates nobody, which is the safe, truthful state.

Clerk issues RS256 JWTs (session tokens). To wire this template:
  1. Fetch and cache the JWKS at  https://{frontend_api}/.well-known/jwks.json  (your Clerk Frontend API
     host, e.g. your-app.clerk.accounts.dev; confirm the current path in the Clerk docs).
  2. Verify the token signature against the key whose `kid` matches the JWT header.
  3. Check  iss == "https://{frontend_api}",  exp not past, and (Clerk-specific) the `azp` authorized
     party against your allowed origins if you use it.
  4. Return  ok({"id": claims["sub"], ...})  ("sub" is the Clerk user id).
"""

import re

from honest_type import err, fault, ok  # noqa: F401  (ok is used once resolve_actor is wired)

# A Clerk session token on the wire: a JWT — three dot-separated base64url segments.
_JWT = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")


def _is_jwt(token):
    return isinstance(token, str) and bool(_JWT.match(token))


def clerk_provider(frontend_api):
    """Build a Clerk AuthProvider TEMPLATE. `frontend_api` is your Clerk Frontend API host (the issuer
    and JWKS origin). Fill in `resolve` before use."""

    def resolve(token):
        # TEMPLATE — fail closed until wired. Verify the JWT against
        #   https://{frontend_api}/.well-known/jwks.json  and check iss/exp (and azp if used), then:
        #     return ok({"id": claims["sub"], "session": claims.get("sid")})
        return err(fault("unauthenticated", "clerk provider is a template and is not wired yet", "unauthenticated"))

    def test_tokens(class_name, context):
        # TEMPLATE — once resolve is wired, mint a real session token per class from a Clerk test
        # instance (valid / revoked / expired / malformed / missing / forged).
        return {"missing": None}.get(class_name)

    return {
        "name": "clerk",
        "actor_recognizer": _is_jwt,
        "resolve_actor": resolve,
        "test_token_generator": test_tokens,
        "fault_mapping": {"unauthenticated": 401, "forbidden": 403, "conflict": 409},
    }
