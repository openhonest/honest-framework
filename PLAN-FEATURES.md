# Build Plan — honest-features

**Status:** not started (this document is for review before any code changes).
**Spec:** `specs/02-code-quality/honest-features-architecture.md`.
**Finding in one line:** the module is almost entirely built and already passes all five gates; there is exactly **one** real implementation gap, and the rest of the spec is adopter-layer or explicitly deferred.

---

## What is already built (verified, not recalled)

The nine library functions the spec's §11 reference-implementation table names are all present, and the module passes all five gates today:

| Gate | Result |
|---|---|
| honest-check lint | 0 errors, 0 warnings |
| coverage | 100% line + branch |
| value oracle | part of 294/294 across the tree |
| feature bijection | 9 functions = 9 scenarios |
| conformance laws | 10/10 |

Surface (`src/honest_features/`): `validate_vocabulary`, `initial_state`, `feature_state` (vocabulary.py); `validate_toggle`, `apply_toggle` (toggle.py); `build_signature`, `verify_signature` (signature.py); `changed_event`, `evaluated_event` (events.py). `verify_signature` already uses `hmac.compare_digest` and enforces the timestamp replay window (§5.2, §10.2). The honest-check rules **HC-HF001** and **HC-HF002** (§7) exist in honest-check.

So this is a **hardening + verification** pass, not a build.

---

## The one real gap — `validate_vocabulary` is structurally incomplete

`validate_vocabulary` enforces the two *semantic* rules from the §2.1 table (a `states` set of at least two members; an `initial_value` that is one of them) but not the *structural* rules from §2.1 and §10.2. Probed against malformed vocabularies:

| Malformed entry | Spec says | Current behaviour |
|---|---|---|
| extra key (`owner`) | §2.1 "No other keys are permitted" | **ACCEPTED** (should reject) |
| missing `initial_value` | §10.2 "a plain dict with `states` and `initial_value` per entry" | **RAISES `KeyError`** (should be a clean `invalid_vocabulary` fault) |
| `states` is a list, not a set | §10.2 "`states` (set)" | **ACCEPTED** (should reject) |
| `initial_value` is not a str | §10.2 "`initial_value` (str)" | rejected today, but only incidentally (the non-str is not in `states`) |

A malformed `FEATURES` is exactly the class of bug this validator exists to catch, so leaving it partial defeats its purpose. This is the whole of the implementation work.

### Plan to close it (red-first, per house rule)

1. **RED** — add conformance laws in `conformance/laws_hf.py` and portable value cases in `conformance/suite.json` asserting `validate_vocabulary` returns an `invalid_vocabulary` client fault (never raises) for each: an entry with a key other than `states`/`initial_value`; an entry missing `states`; an entry missing `initial_value`; a `states` that is not a set; an `initial_value` that is not a str. Confirm they fail against the current code.
2. **GREEN** — harden `validate_vocabulary` to check each entry's key set is exactly `{"states", "initial_value"}`, `states` is a `set` with at least two members, and `initial_value` is a `str` in `states` — collecting offenders into the existing `invalid_vocabulary` fault detail (no exceptions escape; pure).
3. **Feature bijection** — `validate_vocabulary` already has a scenario; extend its `Then` wording to cover the structural rules. No new function, so the 9 = 9 bijection holds.
4. **Re-gate** — lint, `coverage-all.sh honest-features` (must stay 100%), value oracle, feature-gate, `mutate.py features:vocabulary.py` (must be mutation-adequate).
5. **Commit** `impl:` — one commit, the vocabulary hardening.

---

## Explicitly out of scope (adopter-layer or deferred by the spec)

The spec §11 is explicit: the package "ships pure functions only; the application supplies the `FEATURES` vocabulary, holds the state value, and wires the route." So these are **not** honest-features module work:

- **The toggle HTTP route (§5.3)** and **secret loading (§5.4)** — the integration boundary; the app wires it (illustrative FastAPI in the spec).
- **The caller CLI/helper (§5.5)** — an application tool (`tools/feature_toggle.py`), not the library.
- **Handler tables (§4)** — adopter code; the pattern, not a shipped primitive.
- **A/B middleware (§9)** — the spec states outright it "requires no changes to honest-features"; it is optional middleware above the flag layer.
- **Test-time exhaustive combination generation (§6.3)** — honest-test's responsibility (it enumerates each flag's Set); verify it exists there, but it is not honest-features surface.

If any of these should ship as framework code rather than adopter examples (e.g. a provider-style route helper, mirroring what we did for auth's `dev_auth_provider` and the provider templates), that is a **separate decision** to make explicitly, not part of this pass.

---

## Cross-module integration to verify (read-only, no code)

- **honest-check HF001/HF002** — present; confirm they are mutation-adequate in honest-check's own gate (they are honest-check's rows, not features').
- **honest-observe events** — `changed_event`/`evaluated_event` produce the §8.1/§8.2 shapes; confirm the event_type strings match (`hf.features.changed`, `hf.features.evaluated`).
- **honest-test §6.3** — confirm combination generation over a flag vocabulary exists in honest-test.

Findings that turn out to be gaps get filed against the owning module (honest-test / honest-observe / honest-check), not folded into features.

---

## Definition of done

- `validate_vocabulary` rejects every malformed vocabulary in the table above with a clean `invalid_vocabulary` fault and raises nothing; laws + value cases prove it; all five gates green.
- The `SPEC-CONFORMANCE-AUDIT.md` honest-features row is updated from "9/9 lib functions" to note the vocabulary validator is now complete against §2.1/§10.2, with Full/Complete still correctly deferred to the app layer per §11.
- The three cross-module checks above are recorded as satisfied, or their gaps filed against the owning module.
