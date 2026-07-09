"""Firebase Authentication provider TEMPLATE (adopter scaffold — outside the framework gate).

This is not a shipped provider. Copy it into your application and complete `resolve_actor`. The framework
ships no default provider (spec section 3.2). `resolve_actor` FAILS CLOSED until you wire it — an
unconfigured provider authenticates nobody, which is the safe, truthful state.

Firebase issues RS256 ID tokens (JWTs) signed with Google's rotating keys. To wire this template:
  1. Fetch and cache Google's public signing certificates (the securetoken system service account x509
     certs; confirm the current endpoint in the Firebase "Verify ID Tokens" docs).
  2. Verify the token signature against the cert whose `kid` matches the JWT header.
  3. Check  iss == "https://securetoken.google.com/{project_id}",  aud == project_id,  and exp not past.
  4. Return  ok({"id": claims["sub"], ...})  ("sub" is the Firebase user uid).
"""

import re

from honest_type import err, fault, ok  # noqa: F401  (ok is used once resolve_actor is wired)

# A Firebase ID token on the wire: a JWT — three dot-separated base64url segments.
_JWT = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")


def _is_jwt(token):
    return isinstance(token, str) and bool(_JWT.match(token))


def firebase_provider(project_id):
    """Build a Firebase AuthProvider TEMPLATE. `project_id` is your Firebase project id (the expected
    `aud` claim and the issuer suffix). Fill in `resolve` before use."""

    def resolve(token):
        # TEMPLATE — fail closed until wired. Verify the ID token against Google's public certs and
        # check iss == "https://securetoken.google.com/{project_id}", aud == project_id, exp, then:
        #     return ok({"id": claims["sub"], "email": claims.get("email")})
        return err(fault("unauthenticated", "firebase provider is a template and is not wired yet", "unauthenticated"))

    def test_tokens(class_name, context):
        # TEMPLATE — once resolve is wired, mint a real ID token per class from the Firebase Admin SDK
        # against a test project (valid / revoked / expired / malformed / missing / forged).
        return {"missing": None}.get(class_name)

    return {
        "name": "firebase",
        "actor_recognizer": _is_jwt,
        "resolve_actor": resolve,
        "test_token_generator": test_tokens,
        "fault_mapping": {"unauthenticated": 401, "forbidden": 403, "conflict": 409},
    }
