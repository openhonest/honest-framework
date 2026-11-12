# EXPLORATION: Facade pattern at every critical boundary

**Status:** Exploration. Surfaced 2026-05-09 during the Open VRM library-choice discussion. Candidate for promotion to a framework-level architectural directive (or honest-check rule) once validated across multiple projects.

**Update 2026-06-15:** A narrow slice of this pattern is now normative. Dogfooding honest-check against honest-test's browser harness (`UserAction` / `UserView`) surfaced the tension between capability-hiding facades and HC-P003 (no classes). The resolution: a class carrying the `honest:boundary-facade` pragma is a sanctioned HC-P003 exception. See `specs/02-code-quality/honest-check-architecture.md` §5.3.1. This covers only the *capability-hiding* aspect of the facade pattern; the *swappability / sole-importer / config-dispatch* aspects described below remain exploration and are listed there as future statically-verified obligations of the pragma.

## The pattern

Every **critical boundary** between honest application code and an external dependency or substitutable service is mediated by a single-module facade that:

1. Exposes a canonical, dependency-free function signature (pure where possible; plain dicts in and out).
2. Has exactly one default implementation in the same module group.
3. Is replaceable via dict-dispatch through configuration. The active implementation lives in `app.state.<facade>` (or equivalent), wired at lifespan startup.
4. Is the only place that imports the underlying library.
5. Is enforced architecturally: a grep for the underlying library's import outside the facade module returns zero matches.

The facade is dict-dispatch applied to architectural seams. The honest principle adjacent to this is "I/O at the boundary." This pattern goes one step further: even at the boundary, the dependency is hidden behind a substitutable contract.

## Why this matters

Critical boundaries are where lock-in accumulates. A PDF library's API spreads across templates and route handlers. An email client's SDK spreads across notification paths. An object storage SDK leaks into business logic. Without a facade, replacing any of these becomes a multi-week refactor. With a facade, the swap is a config change at lifespan startup, and the architectural test guarantees no implementation-specific code has leaked outside the facade module.

The pattern also enables a deferred-decision discipline: choose a v1 default with operational simplicity (e.g., Postgres BYTEA for object storage), and migrate when scale demands it (e.g., to R2). The migration cost is bounded because the facade has already constrained where implementation knowledge is allowed to live.

## Candidate critical boundaries

Surfaced from Open VRM but generalizable:

| Boundary | Default | Alternative when |
|---|---|---|
| Object storage | Postgres BYTEA (separate database) | R2 / S3 when backup window or capacity demands |
| Virus scan | ClamAV | Commercial scanner when detection rate insufficient |
| PDF generation | WeasyPrint | Playwright / Gotenberg when modern CSS rendering needed |
| Email delivery | Resend | Postmark / SES at scale or cost ceiling |
| Scheduler | APScheduler in-process | Redis-backed RQ / arq when multi-replica |
| Notification queue | procrastinate (Postgres) | Celery / dramatiq when cross-language workers needed |
| Observability | Sentry | OpenTelemetry / Grafana stack at compliance ceiling |
| Outbound HTTP | httpx | Rare to switch; facade is mostly for testing seams |

A boundary qualifies as "critical" if:

1. It is an external service or library with at least one viable alternative.
2. Lock-in to a specific implementation would be expensive (cost, vendor risk, capability gap, regulatory constraint).
3. The application code does not depend on the implementation's idiosyncrasies, only on the canonical contract.

## Contract shape

The contract module exposes the function signatures and a configuration entry point:

```python
# app/<facade>/__init__.py
# The contract is documented here; signatures only.
# Implementation is registered at lifespan startup.

# Example for object storage:
def store(content: bytes, *, key: str, content_type: str) -> StorageResult: ...
def fetch(key: str) -> bytes: ...
def presigned_url(key: str, *, ttl_seconds: int) -> str | None: ...
def delete(key: str) -> None: ...
```

Implementations sit alongside in the same package:

```
app/<facade>/__init__.py        # contract module
app/<facade>/postgres.py        # default implementation
app/<facade>/r2.py              # alternative implementation
```

Wiring at lifespan startup binds one implementation:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.storage = postgres_storage  # or r2_storage based on config
    yield
```

Route handlers and pure logic functions go through the wired implementation:

```python
@router.get("/evidence/{evidence_id}")
async def download_evidence(request: Request, evidence_id: str):
    storage = request.app.state.storage
    return Response(storage["fetch"](evidence_id), ...)
```

For tests, swap by setting `app.state.storage = test_storage_double` in a fixture.

## Architectural enforcement

For every facade, an enforcement test:

- A grep for the underlying library import (e.g., `import boto3`, `from weasyprint`) outside `app/<facade>/<impl>.py` returns zero matches.
- A grep for direct access to the facade's underlying resource (e.g., the `evidence_files` table for storage) outside the facade module returns zero matches.

Each new facade adds one new enforcement scenario.

## Why this might warrant formalization

If validated across two or more projects, this could become:

- A **Honest Code principle** (a 17th): "Substitutable dependencies live behind dict-dispatch facades."
- An **honest-check rule** (HC-P013 or similar): static check that external library imports are concentrated in single facade modules.
- A **framework-level architectural directive** in `honest-framework-spec.md`, alongside the boundary classification and append-only ledger patterns.

## Open questions

1. Where is the line between "critical" (warrants facade) and "incidental" (direct usage acceptable)? Possible heuristic: any external dependency with more than one viable alternative, OR any dependency whose failure mode requires substitution under operational pressure.

2. Does the facade pattern conflict with "no unnecessary complexity" if the swap genuinely never happens? Counter-argument: the architectural enforcement test is the value, not the swap. Containment of dependency knowledge is itself the win, regardless of whether replacement ever happens.

3. Should the facade's contract be expressed in honest-type vocabulary form, with classify() at the facade boundary? This would make the facade contract statically verifiable in addition to architecturally enforced. Worth exploring once honest-type's classify() is in widespread project use.

4. How does this pattern interact with chain composition? A chain step that calls a facade is effectively a chain step calling another (smaller) chain. Worth examining whether chain composition naturally subsumes this pattern at scale.

## Status

Exploration. Validated once (Open VRM, May 2026). Needs at least one or two more project validations before promotion to a formal Honest Code principle or honest-check rule.

Promote to formal status when:

- A second project independently arrives at the same pattern under different constraints.
- The architectural enforcement test catches a real regression (someone tries to import the underlying library outside the facade) at least once.
- The migration story (config-flip swap of an implementation) is exercised end-to-end on at least one boundary.
