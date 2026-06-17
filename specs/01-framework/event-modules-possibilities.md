# Event-Driven Module Possibilities

Working list of modules that fall naturally out of the **honest-observe** canonical log foundation (append-only event log + canonical envelope + translators + identity binding + projections). Every entry below is the same pattern: a recognizer vocabulary + a set of projections. No new storage. No new log semantics. Once honest-observe exists, each of these is days to weeks, not months.

Organized by category. Modules already spec'd are listed first for context. The rest are candidates.

---

## Already spec'd

See `specs/01-framework/event-modules-spec.md`.

| Module | One-line | Status |
|---|---|---|
| honest-publish | Pub-sub, fan-out delivery | Spec drafted |
| honest-queue | Work queue, competing consumers, retry/DLQ | Spec drafted |
| honest-itil | ITIL records as derived views | Spec drafted |
| honest-forecast | Capacity planning via pure reductions + pluggable forecasters | Spec drafted |

---

## Operations & reliability

| Module | What it does | Why it's low-hanging |
|---|---|---|
| **honest-runbook** | Self-healing. Incident recognizer matches runbook → emits `change.requested` → approval link → chain executes. Runbook-as-data. | Runbook is a chain. Incident matching is a recognizer. No orchestrator. |
| **honest-chaos** | Chaos engineering. Fault injection events, blast-radius measurement, experiment results as projections. | Experiments are event streams. No external chaos platform needed. Replaces Gremlin/Chaos Monkey. |
| **honest-schedule** | Cron + DAG job scheduling. Every run is an event. Missed runs detectable by recognizer. Dependencies as handler chains. | Airflow with 5% of the code. Job dependencies fall out of chain semantics. |
| **honest-incident-retro** | Post-mortems auto-generated. Timeline = filter log by incident window. Contributing factors = recognizer over related events. | Replaces the Google Doc. Timeline already exists. |
| **honest-detect** | SIEM-lite. Recognizers for suspicious patterns ("5 failed logins then success from new IP"). Windowed correlation rules. Alert generation as events. | Correlation is recognizer composition. No separate SIEM. |
| **honest-health** | Liveness/readiness derived from recent event activity. "Service is healthy iff recent events match expected pattern." | No separate health-check endpoint needed. Pattern is already in the log. |
| **honest-rate** | Rate limiting. Token bucket / leaky bucket as pure functions of windowed history. | Decisions are pure. Redis only needed for shared state across nodes. |

## Security & identity

| Module | What it does | Why it's low-hanging |
|---|---|---|
| **honest-session** | Sessions as projections over auth events (login, refresh, logout, revoke). Current sessions = fold. Revocation = recognizer. | Replaces session stores. Naturally auditable. |
| **honest-authz** | Every permission check emits a decision event. Policy-as-code = recognizers. Decisions replayable against historical log when policies change. | Huge compliance win. Audit answers "would this policy have denied X last quarter?" with one projection. |
| **honest-vault** | Secrets access as events. Every read is logged. Rotation triggers as recognizers ("any secret unused for 90 days"). | Access audit is free. Policy compliance is a projection. |
| **honest-consent** | GDPR/CCPA. Every grant/revoke is an event. Current consents = projection. DSAR fulfillment = `filter(events, user=X)`. | Regulatory requirement. Trivial once log exists. |
| **honest-privacy** | PII access audit, data retention, right-to-be-forgotten. | Overlaps with consent + audit. Could be one module or three. |

## Compliance & audit

| Module | What it does | Why it's low-hanging |
|---|---|---|
| **honest-audit** | SOC2 / ISO 27001 / HIPAA / GDPR trails. Every access, every change, every data touch in log. Audit reports as projections. | Regulated industries pay anything for this. Already in the log. |
| **honest-compliance** | Policy-as-code. "No prod deploy without two approvers." "No change during freeze." Policy checks = pure functions over event history. Violations emit events that honest-itil treats as incidents. | Continuous compliance instead of quarterly audits. |
| **honest-lineage** | Data lineage. Every write emits a lineage event. Downstream impact analysis = graph traversal over the log. Schema-change blast radius free. | Replaces Collibra/Alation-lite for the 80% case. |

## Business & finance

| Module | What it does | Why it's low-hanging |
|---|---|---|
| **honest-ledger** | Double-entry accounting. Every journal entry is an event. Trial balance, P&L, cash flow as projections. Works for GL, crypto, any value tracking. | THE original event-sourced system. $30B+ ERP category still running on 40-year-old code. Strategic moat. |
| **honest-meter** | Usage-based billing. Every metered event (API call, GB-hour, compute seconds). Invoices = `reduce(events, period, customer)`. | Billing systems are nightmare sync jobs between product + accounting. This eliminates the gap. |
| **honest-subscription** | Lifecycle events (trial → active → paused → canceled → reactivated). Current status = fold. MRR/ARR = projection. | Chargebee/Recurly replaced. Every SaaS needs this. |
| **honest-tax** | Every taxable event logged. Jurisdiction rules as recognizers. Filings derived from projections. | Avalara-lite. Audit trail is free. |
| **honest-revenue** | Revenue recognition (ASC 606, IFRS 15). Event log gives perfect audit trail. Deferred revenue = projection over lifecycle events. | Sarbanes-Oxley sign-off becomes trivial. |
| **honest-commission** | Sales commission calculation. Attribution + payout rules as projections. | CaptivateIQ-lite. Disputes resolved by replay. |
| **honest-cost** | FinOps. Showback/chargeback by tag is a reduction. Unit economics (cost per request, cost per tenant) are ratios of reductions. | Most companies do this in spreadsheets. |

## Product & growth

| Module | What it does | Why it's low-hanging |
|---|---|---|
| **honest-analytics** | Funnels, cohorts, retention. Cohort analysis = `pure_fn(cohort_recognizer, events, window)`. | Replaces Mixpanel/Amplitude with ~300 lines. |
| **honest-feature** | Feature flags + A/B test evaluation. Flag decision is pure given user context. Experiment results = reductions grouped by variant. | LaunchDarkly/Statsig replaced by TypedDict + two pure functions. |
| **honest-segment** | User segmentation. Segment membership = recognizer over user events. | No separate CDP (customer data platform). |
| **honest-personalize** | Content personalization based on user event history. Recommendations as projections. | Recommendation engines as projections. |
| **honest-onboard** | Onboarding funnel as event sequences. Completion status = projection. Drop-off detection = recognizer. | Instrumented onboarding without any new instrumentation. |
| **honest-retention** | Churn prediction. Event patterns predicting churn are recognizers. | Derivable from the analytics events. |
| **honest-referral** | Referral tracking, viral loops. Attribution chains from referral events. | Attribution arguments resolved by replay. |

## User-facing ops

| Module | What it does | Why it's low-hanging |
|---|---|---|
| **honest-notify** | Every email/SMS/push is an event. Delivery status loops back. Preferences as projections. | No more "did we send the welcome email?" debugging. |
| **honest-activity** | Activity feed ("John commented on X"). Pure projection over user events. | Trivial once events are in the log. |
| **honest-inbox** | In-app notification center. Projection of notification events filtered by user. | Unread counts = fold. Mark-as-read = event. |
| **honest-oncall** | On-call schedules, escalation, pages. Schedule as event stream. Acknowledgments as events. | PagerDuty-lite. |
| **honest-chatops** | Slack/Teams bot reads the log, runs commands. Commands emit events; responses render projections. | Log is already the source; bot is just a UI over it. |

## Data & integration

| Module | What it does | Why it's low-hanging |
|---|---|---|
| **honest-etl** | ETL pipelines as event handlers. Source events → transform chains → destination events. | All typed, all testable without mocks. |
| **honest-cdc** | Change data capture. DB changes as events. Downstream derivations pure. | Debezium-lite. |
| **honest-sync** | Cross-system synchronization. Overlaps with honest-observe §8c (cross-system ingestion). |  |

## Self-documenting

| Module | What it does | Why it's low-hanging |
|---|---|---|
| **honest-changelog** | Auto-generated from `change.applied` events by release window. | No more "update CHANGELOG.md" PRs. |
| **honest-adr** | Architectural decision records as events. "Why did we decide X?" = recognizer query. Living docs that can't lie. | Docs rot. Projections over events can't rot. |

## Testing

| Module | What it does | Why it's low-hanging |
|---|---|---|
| **honest-replay** | Capture production event streams (anonymized), replay against staging. "Does this code handle last Tuesday's traffic?" becomes a one-liner. | Nothing on the market does this well. Developer-love-at-first-sight feature. |
| **honest-property** | Property-based testing using event fixtures from production. | Real-world fuzz corpus is the log. |

## Foundational (likely used by many others)

| Module | What it does | Why it's low-hanging |
|---|---|---|
| **honest-state-machine** | Any aggregate's current state = `fold(events, initial_state)` with transition recognizers. | Used by subscription, session, ticket, order, wizard, deploy. Ship this early. |
| **honest-workflow** | BPMN / workflow engine replacement. Workflows = chains. Current step = projection. | Camunda/Temporal replaced. Overlaps with state-machine + runbook. |

---

## Strategic framing

Every category listed has an existing $1B–$30B tooling market. Those markets exist **because the tooling maintains parallel state that drifts from reality**. Honest Code's thesis (the log is the system of record, views are pure reductions) kills the drift. So this is not "twelve small wins." This is twelve entrances into twelve established markets, all from the same foundation.

The moat: once a customer has the canonical log, adding the next module is hours, not months. Switching costs accumulate in our favor. A competitor building honest-ledger from scratch has to solve all the foundational problems honest-observe already solved.

The category name worth claiming: **declarative operational software**.

---

## Suggested prioritization

Beyond the four already spec'd (honest-publish, honest-queue, honest-itil, honest-forecast), the three highest-leverage to spec next:

1. **honest-state-machine** — foundational; unblocks half of everything else. Ship first.
2. **honest-ledger** — biggest market; clearest "obvious in retrospect" narrative; strongest moat.
3. **honest-replay** — no real competitor; developer-love-at-first-sight; huge book/article material.

Second tier (each opens a distinct established market):

4. **honest-audit** — regulated industries entry point
5. **honest-meter** — SaaS billing entry point
6. **honest-authz** — identity/security entry point
7. **honest-notify** — universal need, universally broken

---

## What NOT to spec (yet)

- Anything that requires serious ML (personalization, churn prediction, anomaly detection on the statistical side). These *use* the log but the value is in the math library, not the framework primitive.
- Anything that needs regulatory certification (HIPAA-certified hosting, PCI-DSS Level 1). The framework enables compliance; certification is an operator concern.
- Anything that requires UI design chops beyond rendering projections (full dashboard builder, drag-and-drop workflow designer). The framework gives the data foundation; UI is separate work.

---

## Open questions (cross-cutting)

1. **Module boundaries:** some categories overlap (honest-consent / honest-audit / honest-privacy; honest-subscription / honest-ledger / honest-meter). Collapse into larger modules, or keep distinct vocabularies? Leaning: keep distinct vocabularies, share projections where natural.
2. **Packaging:** is each module a separate Python/JS package, or does `honest-py` ship them all? Leaning: separate packages so users only install what they need; meta-package `honest-py-all` for convenience.
3. **Documentation shape:** each module needs its own architecture spec similar to honest-observe-architecture.md. That is ~1500 lines × 20+ modules = a lot. Spec generation from recognizer vocabularies?
4. **Conformance:** how do we certify that an implementation of honest-subscription matches the spec? Likely via a shared conformance suite in the style of `honest-conformance-suite.md`.
