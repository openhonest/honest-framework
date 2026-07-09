"""Supabase Auth provider TEMPLATE (adopter scaffold — outside the framework gate).

This is not a shipped provider. Copy it into your application and complete `resolve_actor`. The framework
ships no default provider (spec section 3.2). `resolve_actor` FAILS CLOSED until you wire it — an
unconfigured provider authenticates nobody, which is the safe, truthful state.

Supabase issues JWTs, but the SIGNING SCHEME depends on your project, and Supabase has been migrating it:
  - Legacy projects sign with a shared HS256 secret (the project JWT secret). You verify with that secret.
  - Newer projects use asymmetric keys published at a JWKS endpoint and verify by public key (RS256/ES256).
Confirm which your project uses in the Supabase dashboard before wiring — do not assume one or the other.

To wire this template:
  1. Determine your signing scheme (shared HS256 secret, or asymmetric keys via the project JWKS).
  2. Verify the token signature accordingly.
  3. Check  iss == "https://{project_ref}.supabase.co/auth/v1"  and exp is not past (Supabase access
     tokens carry aud == "authenticated"; confirm against your project's token).
  4. Return  ok({"id": claims["sub"], ...})  ("sub" is the Supabase user id).
"""

import re

from honest_type import err, fault, ok  # noqa: F401  (ok is used once resolve_actor is wired)

# A Supabase access token on the wire: a JWT — three dot-separated base64url segments.
_JWT = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")


def _is_jwt(token):
    return isinstance(token, str) and bool(_JWT.match(token))


def supabase_provider(project_ref):
    """Build a Supabase AuthProvider TEMPLATE. `project_ref` is your project ref (the issuer host). Wire
    `resolve` with the signing scheme your project actually uses before relying on it."""

    def resolve(token):
        # TEMPLATE — fail closed until wired. Verify the JWT with your project's signing scheme (shared
        # HS256 secret OR asymmetric JWKS), check iss/exp, then:
        #     return ok({"id": claims["sub"], "email": claims.get("email"), "role": claims.get("role")})
        return err(fault("unauthenticated", "supabase provider is a template and is not wired yet", "unauthenticated"))

    def test_tokens(class_name, context):
        # TEMPLATE — once resolve is wired, mint a real token per class from a Supabase test project
        # (valid / revoked / expired / malformed / missing / forged).
        return {"missing": None}.get(class_name)

    return {
        "name": "supabase",
        "actor_recognizer": _is_jwt,
        "resolve_actor": resolve,
        "test_token_generator": test_tokens,
        "fault_mapping": {"unauthenticated": 401, "forbidden": 403, "conflict": 409},
    }
