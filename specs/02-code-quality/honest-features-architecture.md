# honest-features: Architecture Specification

**Version:** 0.1 (Draft)
**Date:** March 2026
**Status:** Active
**Author:** Adam Zachary Wasserman

---

## 1. Purpose and Scope

honest-features is the feature flag subsystem of the Honest Framework. It provides runtime-togglable feature flags with no rebuild, no redeploy, and no environment variable mutation.

The core principle: a feature flag is a named state that routes execution to a handler. The flag vocabulary is static code. The flag state is ephemeral runtime data. The two concerns are fully separated.

### 1.1 What honest-features Solves

Conventional feature flags use environment variables. Changing a flag requires a process restart or a redeploy. Testing flag combinations requires environment manipulation that bleeds between test cases. The flag set is implicit — you must read the environment to know what exists.

honest-features eliminates all of these problems:

- Flags are declared in code as a vocabulary. The full set is always visible.
- State is ephemeral in-memory data, initialized from defaults at startup.
- State changes happen via a single HMAC-protected API endpoint. No restart. No redeploy.
- Tests set flag state directly on the in-memory dict. No environment manipulation.

### 1.2 What honest-features Does Not Cover

- Persistent flag state across process restarts — state resets to defaults on restart by design. Persistence belongs in honest-persist if required.
- User-level or tenant-level flag targeting — honest-features is process-level. Targeting logic belongs in application code above the flag layer.
- Audit logging of flag changes — emit to honest-observe; honest-features does not own observability.
- Authentication of the HMAC shared secret — key distribution is out of scope. The secret is loaded from configuration at startup.

### 1.3 Relationship to Other Specs

- **honest-type:** The flag vocabulary is a honest-type vocabulary. Flag names and states are Sets. honest-check can verify that every call site references a declared flag name and a declared state.
- **honest-check:** Provides rule HF001 (see §7): every `feature_state()` call site must reference a flag name declared in `FEATURES`.
- **honest-test:** Tests set `_state` directly. honest-test fixture support resets `_state` to defaults between test cases.
- **honest-observe:** State change events and evaluation events are emitted to the honest-observe event log. honest-features emits; honest-observe owns the log.

---

## 2. The Flag Vocabulary

Flags are declared as a plain dict. The vocabulary is the complete, enumerable set of flags the application recognizes. It is declared once, in one place, at module scope.

```python
# features.py

FEATURES: dict[str, dict] = {
    "new_checkout":  {"states": {"on", "off"},           "default": "off"},
    "dark_mode":     {"states": {"on", "off"},           "default": "off"},
    "pricing":       {"states": {"a", "b", "control"},   "default": "control"},
}
```

### 2.1 Vocabulary Rules

Each entry in `FEATURES` must declare:

| Key | Type | Description |
|---|---|---|
| `states` | `set[str]` | The complete set of valid states for this flag. Must contain at least two members. |
| `default` | `str` | The state the flag holds at process startup. Must be a member of `states`. |

No other keys are permitted at the vocabulary level. Metadata (owner, description, created date) belongs in a separate registry outside the runtime vocabulary.

### 2.2 Vocabulary as honest-type Integration

The `states` set of each flag is a Set recognizer in the honest-type sense: finite, listable, testable in full. `feature_state()` returns a value that is guaranteed to be a member of the declared states set. Downstream handler tables are guaranteed to have a handler for every possible flag state.

---

## 3. Flag State as a Value

Flag state is ephemeral, and it is a **value**, not module state — the single mutator is the toggle endpoint (the "dynamic config" kind in honest-state's taxonomy). `initial_state` builds it from the vocabulary defaults; the application's startup holds it and the toggle boundary updates it. Threading the state as a value is what keeps `feature_state` a pure lookup and lets honest-features pass its own gate (no hidden module mutable state, the auth/registry pattern).

```python
def initial_state(features: dict) -> dict:
    """The flag state at startup: each flag at its declared default. Pure, no I/O."""
    return {flag: spec["default"] for flag, spec in features.items()}

def feature_state(state: dict, flag: str) -> str:
    """The current state of a flag, read from the state value. Pure.

    A flag not declared in FEATURES is a programming error caught statically by HF001 (§7), so a
    flag that reaches here is always present.
    """
    return state[flag]
```

`feature_state` is a pure lookup over the state value it is handed. No I/O. No side effects. No module global. It is the only interface downstream code uses to read flag state.

### 3.1 State Initialization

`initial_state(features)` copies each flag's declared default. No environment variables, config files, or database are read — initialization is deterministic and requires no I/O. The application calls it once at startup and holds the returned value.

### 3.2 State Reset

There is no persistence: a fresh `initial_state(features)` is always the declared defaults, so a restarted process starts from a known state. Operators who want persistent flag state persist it externally and replay the toggles after startup.

---

## 4. The Handler Table Pattern

Downstream code never calls `if/else` on flag state. It uses a handler table: a dict mapping each possible flag state to a handler function. `feature_state()` returns the current state; the handler table dispatches to the correct handler. This is the dict-dispatch pattern from Honest Code applied to feature branching.

```python
# checkout.py

from features import feature_state

def _new_checkout_handler(manifest: dict) -> dict:
    ...

def _legacy_checkout_handler(manifest: dict) -> dict:
    ...

CHECKOUT_HANDLERS: dict[str, Callable] = {
    "on":  _new_checkout_handler,
    "off": _legacy_checkout_handler,
}

def handle_checkout(manifest: dict) -> dict:
    return CHECKOUT_HANDLERS[feature_state("new_checkout")](manifest)
```

### 4.1 Handler Table Rules

- The handler table must declare a handler for every state in the flag's vocabulary. A missing state causes a `KeyError` at dispatch time, not a silent incorrect branch. This is intentional.
- Each handler is a pure function. It knows nothing about feature flags. It receives a manifest and returns a result.
- The handler table is declared at module scope, not constructed dynamically.

### 4.2 Multi-State Flags

Multi-state flags (A/B/control, tier pricing, etc.) require no special treatment. The handler table simply has more entries.

```python
PRICING_HANDLERS: dict[str, Callable] = {
    "a":       pricing_handler_a,
    "b":       pricing_handler_b,
    "control": pricing_handler_control,
}

def handle_pricing(manifest: dict) -> dict:
    return PRICING_HANDLERS[feature_state("pricing")](manifest)
```

---

## 5. The Toggle API

A single endpoint accepts state changes for all flags. The endpoint is polymorphic over the vocabulary — it does not know which flag it is setting. Adding a new flag to `FEATURES` requires zero changes to the endpoint.

### 5.1 Endpoint

```
POST /hf/features/set
Content-Type: application/json

{
    "flag":      "new_checkout",
    "state":     "on",
    "timestamp": 1710000000,
    "signature": "<hmac_sha256>"
}
```

**Response on success (200):**

```json
{"flag": "new_checkout", "state": "on", "previous": "off"}
```

**Error responses:**

| Status | Condition |
|---|---|
| 400 | Flag not in `FEATURES` |
| 400 | State not in `FEATURES[flag]["states"]` |
| 400 | Timestamp missing or malformed |
| 403 | Signature invalid |
| 403 | Timestamp outside replay window |

### 5.2 HMAC Signature

The signature is HMAC-SHA256 over the message `"{flag}:{state}:{timestamp}"` using the shared secret.

**Why HMAC over the full payload, not a bearer token:**

A bearer token proves identity but not intent. An intercepted request carrying a valid token can be replayed with a different body. The HMAC signature covers flag, state, and timestamp together. A tampered body invalidates the signature. An intercepted and replayed request is rejected by the timestamp window. The shared secret never travels over the wire.

**Signature construction (caller):**

```python
import hmac, hashlib, time

def build_signature(secret: bytes, flag: str, state: str, timestamp: int) -> str:
    message = f"{flag}:{state}:{timestamp}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()
```

**Signature verification (server):**

```python
import hmac, hashlib

def verify_signature(
    secret: bytes,
    flag: str,
    state: str,
    timestamp: int,
    signature: str,
    now: int,
    window: int = 60,
) -> bool:
    if abs(now - timestamp) > window:
        return False
    message = f"{flag}:{state}:{timestamp}".encode()
    expected = hmac.new(secret, message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

`now` is passed in — reading the clock is I/O and belongs at the boundary, so `verify_signature` stays a pure function the tests can drive at any instant. `hmac.compare_digest` is required: string equality comparison is vulnerable to timing attacks.

honest-features ships these as **pure functions over the state value** — `initial_state`, `feature_state`, `validate_toggle` (the 400 conditions), `apply_toggle`, `build_signature`, and `verify_signature`. The HTTP route below is an integration boundary: it holds the state value, reads the clock and the request, calls the pure functions, and emits the change event. (The FastAPI / pytest / A-B examples in this spec are illustrative integration; they thread the state value rather than a module global.)

### 5.3 FastAPI Implementation

```python
# routes/features.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from features import FEATURES, _state, verify_signature, load_secret

router = APIRouter()

class FeatureToggleRequest(BaseModel):
    flag:      str
    state:     str
    timestamp: int
    signature: str

@router.post("/hf/features/set")
def set_feature(req: FeatureToggleRequest) -> dict:
    if req.flag not in FEATURES:
        raise HTTPException(400, f"Unknown flag: {req.flag}")
    if req.state not in FEATURES[req.flag]["states"]:
        raise HTTPException(400, f"Invalid state '{req.state}' for flag '{req.flag}'")
    if not verify_signature(
        load_secret(), req.flag, req.state, req.timestamp, req.signature
    ):
        raise HTTPException(403, "Invalid or expired signature")
    previous = _state[req.flag]
    _state[req.flag] = req.state
    return {"flag": req.flag, "state": req.state, "previous": previous}
```

### 5.4 Secret Loading

The HMAC secret is loaded from a configuration record at startup. It is never read from an environment variable and never hardcoded.

```python
def load_secret() -> bytes:
    # Load from honest-persist configuration record
    return config_record("honest_features_hmac_secret").encode()
```

### 5.5 Caller Utility

A CLI utility and importable helper are provided for constructing toggle requests:

```python
# tools/feature_toggle.py

import hmac, hashlib, time, requests

def toggle(base_url: str, secret: bytes, flag: str, state: str) -> dict:
    timestamp = int(time.time())
    message = f"{flag}:{state}:{timestamp}".encode()
    signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
    response = requests.post(f"{base_url}/hf/features/set", json={
        "flag": flag, "state": state,
        "timestamp": timestamp, "signature": signature,
    })
    response.raise_for_status()
    return response.json()
```

---

## 6. Testing Integration

Because `_state` is a plain dict, tests manipulate flag state directly. No API calls. No environment manipulation. No process restart.

### 6.1 Direct State Manipulation

```python
from features import _state, FEATURES

def test_new_checkout_on():
    _state["new_checkout"] = "on"
    result = handle_checkout(manifest)
    assert result == expected_new

def test_new_checkout_off():
    _state["new_checkout"] = "off"
    result = handle_checkout(manifest)
    assert result == expected_legacy
```

### 6.2 Reset Fixture

A pytest fixture resets all flags to defaults between test cases:

```python
import pytest
from features import _state, FEATURES

@pytest.fixture(autouse=True)
def reset_features():
    yield
    for flag, spec in FEATURES.items():
        _state[flag] = spec["default"]
```

### 6.3 Testing every combination

Because each flag's states are a finite Set, honest-test can list all combinations and generate a test case for each. For a flag with two states and a handler table with two handlers, honest-test generates two test cases automatically. For three flags each with two states, honest-test generates eight test cases. No test case is written by hand for correctness coverage — the combinations fall out of the vocabulary.

---

## 7. honest-check Integration

### Rule HF001: Undeclared Flag Reference

**Severity:** Error

Every `feature_state("flag_name")` call site must reference a flag name declared as a key in `FEATURES`. A call referencing an undeclared flag is a programming error: it will raise `KeyError` at runtime.

honest-check walks the AST, finds all `feature_state(...)` calls, extracts the string argument, and verifies it is a key in the `FEATURES` dict in the same module or in the imported `features` module.

**Violation example:**

```python
feature_state("not_a_real_flag")  # HC-HF001: 'not_a_real_flag' not in FEATURES
```

### Rule HF002: Missing Handler Table Entry

**Severity:** Warning

A handler table keyed on `feature_state("flag_name")` must contain an entry for every state declared in `FEATURES["flag_name"]["states"]`. A missing entry will raise `KeyError` at dispatch time when the flag enters that state.

---

## 8. honest-observe Integration

honest-features emits two event types to the honest-observe event log.

### 8.1 State Change Event

Emitted synchronously by the toggle endpoint after a successful state change.

```python
{
    "event_type":    "hf.features.changed",
    "flag":          "new_checkout",
    "previous":      "off",
    "state":         "on",
    "timestamp":     1710000000,
    "requesting_ip": "10.0.0.1"
}
```

### 8.2 Evaluation Event

Emitted by `feature_state()` when called within a request context (request_id available in context). Not emitted outside request context to avoid noise in background tasks.

```python
{
    "event_type":  "hf.features.evaluated",
    "flag":        "new_checkout",
    "state":       "on",
    "request_id":  "req_abc123"
}
```

Evaluation events allow operators to correlate flag states with request outcomes in the unified event log.

---

## 9. A/B Testing Middleware

A/B testing is not a core honest-features concern. It is an optional middleware layer that sits above honest-features and uses its primitives. No changes to the honest-features spec are required to support A/B testing.

### 9.1 What A/B Testing Adds

honest-features already provides everything needed for the flag mechanism: a multi-state flag with two or more states, a handler table dispatching to variant implementations, and `hf.features.evaluated` events in the honest-observe event log correlating flag state with request outcomes.

A/B testing adds three concerns on top:

- **Variant assignment:** routing a specific user or session to a specific variant the same way every time
- **Measurement:** correlating variant assignment with outcome metrics in the event log
- **Statistical analysis:** determining when a measured difference is significant

None of these belong in honest-features. All three are middleware concerns.

### 9.2 Flag Declaration

An A/B flag is a standard honest-features multi-state flag:

```python
FEATURES = {
    "checkout_flow": {"states": {"a", "b", "control"}, "default": "control"},
}
```

No special A/B vocabulary is needed. The states are the variants.

### 9.3 Variant Assignment Middleware

The middleware intercepts each request, extracts a stable identity (user ID, session ID, or anonymous token), and deterministically assigns a variant using consistent hashing. The same identity always receives the same variant for the duration of the experiment.

```python
# middleware/ab.py

import hashlib
from features import FEATURES, _state

def assign_variant(flag: str, identity: str) -> str:
    """Deterministically assign a variant for this identity.

    Uses consistent hashing: same identity always returns same variant.
    Does not call the toggle API. Sets state in request context only.
    """
    states = sorted(FEATURES[flag]["states"])  # sort for determinism
    digest = int(hashlib.sha256(f"{flag}:{identity}".encode()).hexdigest(), 16)
    return states[digest % len(states)]


class ABMiddleware:
    """FastAPI middleware for A/B variant assignment.

    Assigns variants for declared A/B flags before the request handler runs.
    Stores assignments in request state for use by feature_state().
    """

    def __init__(self, app, ab_flags: set[str]):
        self.app = app
        self.ab_flags = ab_flags  # flags managed by A/B, not by toggle API

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            identity = extract_identity(scope)  # user_id, session_id, or anon token
            for flag in self.ab_flags:
                variant = assign_variant(flag, identity)
                # Store in request-scoped state, not in global _state
                scope.setdefault("ab_assignments", {})[flag] = variant
        await self.app(scope, receive, send)
```

### 9.4 Request-Scoped State

A/B variant assignment must not mutate the global `_state` dict. The global state is process-level; variant assignment is request-level. The middleware stores assignments in request scope. A request-aware `feature_state()` wrapper reads from request scope first, falling back to global state:

```python
# middleware/ab.py (continued)

from contextvars import ContextVar

_request_assignments: ContextVar[dict] = ContextVar("ab_assignments", default={})

def feature_state_for_request(flag: str) -> str:
    """Return the variant for this flag in the current request context.

    If this flag has an A/B assignment for the current request, return it.
    Otherwise fall back to global feature_state().
    """
    assignments = _request_assignments.get()
    if flag in assignments:
        return assignments[flag]
    from features import feature_state
    return feature_state(flag)
```

Request handlers use `feature_state_for_request()` instead of `feature_state()` when A/B middleware is active. Handler tables are unchanged.

### 9.5 Measurement via honest-observe

`hf.features.evaluated` already emits flag name, state, and request_id for every evaluation. The A/B middleware adds the identity and assignment to the event:

```python
{
    "event_type":   "hf.features.evaluated",
    "flag":         "checkout_flow",
    "state":        "b",
    "request_id":   "req_abc123",
    "ab_identity":  "user_8472",
    "ab_assigned":  true
}
```

Outcome events (conversion, error, duration) are emitted by the application and carry `request_id`. The unified event log joins variant assignment to outcome by `request_id`. No additional instrumentation is needed. The measurement layer is a query against data that is already there.

**Example query:** conversion rate by variant for `checkout_flow`:

```sql
SELECT
    e.state                          AS variant,
    COUNT(DISTINCT o.request_id)     AS conversions,
    COUNT(DISTINCT e.request_id)     AS exposures,
    ROUND(COUNT(DISTINCT o.request_id) * 100.0
          / COUNT(DISTINCT e.request_id), 2) AS conversion_rate_pct
FROM   hf_events e
LEFT JOIN hf_events o
    ON  o.request_id  = e.request_id
    AND o.event_type  = 'checkout.completed'
WHERE  e.event_type  = 'hf.features.evaluated'
AND    e.flag        = 'checkout_flow'
AND    e.ab_assigned = true
GROUP  BY e.state;
```

Statistical significance is computed outside the framework against the query results. The framework provides the data. Analysis is the operator's concern.

### 9.6 Experiment Lifecycle

| Phase | Action |
|---|---|
| **Start** | Register flag in `FEATURES`. Add flag to `ABMiddleware` `ab_flags` set. Deploy. |
| **Running** | Middleware assigns variants. honest-observe accumulates evaluation and outcome events. |
| **Decision** | Query event log. Compute significance. Choose winning variant. |
| **Conclude** | Remove flag from `ab_flags`. Call toggle API to set global state to winning variant. Remove losing handler from handler table in next release. |

The flag does not need to be removed immediately on conclusion. Setting global state to the winning variant via the toggle API stops variant assignment and routes all traffic to the winner while the losing code path is cleaned up in the next release.

### 9.7 Integration Summary

A/B testing requires no changes to honest-features. It requires:

- A multi-state flag in `FEATURES` (standard)
- `ABMiddleware` installed in the application's request pipeline
- `feature_state_for_request()` used in place of `feature_state()` in request handlers
- `ab_assigned: true` added to `hf.features.evaluated` events by the middleware
- A query against the honest-observe event log for measurement

All other honest-features behaviour — HMAC toggle API, handler tables, honest-check rules, honest-test fixtures — is unchanged.

---

## 10. Conformance

### 10.1 Conformance Levels

| Level | Requirement |
|---|---|
| **Core** | `FEATURES` vocabulary dict; `_state` in-memory dict; `feature_state()` lookup; HMAC-protected `/hf/features/set` endpoint with timestamp replay protection; handler table pattern at all flag dispatch points |
| **Full** | Core + honest-observe emission on state change and evaluation; honest-test reset fixture; `reset_features` autouse fixture |
| **Complete** | Full + honest-check HF001 and HF002 rules; honest-test exhaustive combination generation from flag vocabulary |

### 10.2 Conformance Checks

A conformant implementation satisfies all of the following:

- `FEATURES` is declared at module scope as a plain dict with `states` (set) and `default` (str) per entry
- `_state` is initialized from `FEATURES` defaults at import time with no I/O
- `feature_state()` raises `KeyError` for undeclared flag names — not a silent default
- The toggle endpoint verifies HMAC signature using `hmac.compare_digest` — not string equality
- The toggle endpoint enforces a timestamp replay window
- No call site uses `if/else` conditional on flag state — all dispatch is via handler tables
- No flag state is read from environment variables
- Handler tables declare an entry for every state in the corresponding flag's vocabulary

---

## 11. Reference Implementation

The Python/FastAPI reference implementation is at `honest-py/honest/features/`.

Key files:

| File | Purpose |
|---|---|
| `features.py` | Vocabulary, `_state`, `feature_state()`, HMAC utilities |
| `routes/features.py` | FastAPI toggle endpoint |
| `tools/feature_toggle.py` | Caller-side utility |
| `conftest.py` | `reset_features` pytest fixture |
| `tests/test_features.py` | Conformance tests |
