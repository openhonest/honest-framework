# honest-auth provider templates

These are **adopter scaffolds, not shipped providers.** They live outside `src/`, so they are outside
every framework gate (honest-check lint, 100% coverage, value oracle, mutation, bijection) on purpose:
they are starting points you copy into your own application and complete, then gate in *your* repo.

The framework deliberately ships no default provider (spec section 3.2) — a weak default is a false sense
of security. Each template here is a real `AuthProvider` shape with the one hard part left to you.

| File | Factory | Provider |
|---|---|---|
| `auth0.py` | `auth0_provider(domain, audience)` | Auth0 (RS256 JWT, JWKS) |
| `firebase.py` | `firebase_provider(project_id)` | Firebase Authentication (RS256 ID tokens) |
| `supabase.py` | `supabase_provider(project_ref)` | Supabase Auth (JWT; HS256 secret **or** asymmetric JWKS — confirm your project) |
| `clerk.py` | `clerk_provider(frontend_api)` | Clerk (RS256 JWT, JWKS) |

## What is already done for you

- `actor_recognizer` — the JWT wire-format check (three base64url segments). All four are JWT-based.
- `fault_mapping` — the standard `{unauthenticated: 401, forbidden: 403, conflict: 409}`.
- `name` and the provider value's shape.

## What you complete

- **`resolve_actor`** — the boundary validator. It currently **fails closed** (denies every request) until
  you wire the provider's JWKS verification. Each file's docstring lists the exact steps: fetch/cache the
  keys, verify the signature, check `iss`/`aud`/`exp`, map the `sub` claim to your actor.
- **`test_token_generator`** — once `resolve_actor` is real, mint a token per class (valid, revoked,
  expired, malformed, missing, forged) from the provider's test tenant.

## How you know you are done

Run the framework's acceptance check against your completed provider:

```python
from honest_auth import authentication_honesty
result = authentication_honesty(your_provider, context)   # ok(provider) when every token class is honest
```

Until `resolve_actor` is wired, this fails on the `valid` class — the honest signal that the template is
still a template. The URLs and claim names above are the stable patterns; confirm them against each
provider's current documentation before you ship.
