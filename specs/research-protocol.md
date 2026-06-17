# Research Protocol: Honest Framework Development Study

**Version:** 0.1 (Draft)
**Date:** March 22, 2026
**Principal Investigator:** Adam Zachary Wasserman

---

## 1. Research Question

Does architectural philosophy (Honest Code: pure functions, dispatch tables, flat composition, DOM-as-state) produce measurably different outcomes in AI-assisted enterprise framework development compared to conventional architectures, when process discipline is held constant?

Secondary questions:
- What are the activity ratios (specification/coding/refactoring) in AI-assisted framework development from ideation through implementation?
- Do these ratios differ across language implementations of the same specification?
- Does the conformance suite model (spec-as-FP-count) eliminate the need for function point backfiring?
- What is the cost of counteracting gradient descent (refactoring ratio) across languages and teams?

---

## 2. Study Design

### 2.1 The Constant: Framework Specification

The Honest Framework specification defines 12 modules with 50 conformance laws across 3 conformance levels (Core: 20 laws, Full: 42, Complete: 50). The specification is language-agnostic. Each conformance law maps to one or more IFPUG elementary processes (see Appendix A). The spec is the control variable: identical functional requirements across all implementations.

### 2.2 The Variables

| Variable | Type | Values |
|----------|------|--------|
| Architecture | Independent | Honest Code (prescribed) vs. implementor's choice |
| Language | Independent | Python, JavaScript, Ruby, Go, PHP, Elixir |
| Team | Independent | PI (Python), arm's-length teams (other languages) |
| Process discipline | Controlled | Structured AI-SDLC required for all participants |
| AI tools | Controlled | AI coding assistants permitted under SDLC constraints |
| Specification | Controlled | Same conformance suite for all implementations |

### 2.3 Measurement Points

**Primary outcome:** Conformance laws satisfied per FTE-month, by module, by language.

**Secondary outcomes:**
- Activity ratios: specification / coding / refactoring (from commit prefixes)
- Lines of code per conformant law (measures architectural verbosity)
- Time-to-conformance per module (from time logs)
- Defect rate per conformant law (from `fix:` commits)
- Code delete/add ratio (refactoring intensity)
- Test coverage at conformance (automated)

### 2.4 Phases

**Phase 0: Specification completion (current)**
Complete the remaining ~1-5% of specification. Map each conformance law to IFPUG elementary processes. This phase is itself instrumented (AI-assisted ideation and design).

**Phase 1: Python reference implementation (PI solo)**
Build honest-py. All 12 modules. Full conformance suite passing. This establishes:
- Baseline activity ratios for AI-assisted framework development under Honest Code
- Time-to-conformance benchmarks per module
- Reference implementation that other teams can study

**Phase 2: Multi-language implementations (arm's-length teams)**
Other language implementations begin. Each team receives:
- The complete specification
- The conformance suite (adapted to their language's property-based testing framework)
- The structured SDLC requirements
- The commit convention requirements
- Optional: access to the Python reference implementation

Teams are free to choose their own architecture within their language's idioms. Some may follow Honest Code principles; others may use conventional patterns (classes, inheritance, ORMs). This architectural divergence is the independent variable.

---

## 3. Instrumentation

### 3.1 Commit Convention (All Participants)

Every commit message must begin with one of these prefixes:

| Prefix | Category | Description |
|--------|----------|-------------|
| `spec:` | Specification | Changes to .md, .feature, specification documents |
| `design:` | Design | Architecture decisions, diagrams, API design |
| `impl:` | Implementation | New code implementing spec requirements |
| `refactor:` | Refactoring | Restructuring existing code without changing behavior |
| `test:` | Testing | Test code, test infrastructure, coverage improvements |
| `fix:` | Bug fix | Correcting defective code |
| `chore:` | Maintenance | Dependencies, CI/CD, tooling, config |
| `docs:` | Documentation | README, comments, usage examples (not spec) |

**Enforcement:** Pre-commit hook validates prefix. Commits without valid prefix are rejected.

### 3.2 Time Tracking

Session-level time tracking via shell hook:

```bash
# In .zshrc or project hook:
# Logs session start/stop with project and phase context
honest_time_start() {
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) START $1 $(pwd)" >> ~/.honest-research/time.log
}
honest_time_stop() {
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) STOP $1 $(pwd)" >> ~/.honest-research/time.log
}
```

Granularity: session-level (start/stop per work session). Not per-commit.

### 3.3 Conformance Tracking

Each module maintains a conformance status file:

```yaml
# conformance-status.yaml (in each implementation root)
module: honest-type
language: python
laws:
  HT-1: { status: pass, date: 2026-04-01, commit: abc1234 }
  HT-2: { status: pass, date: 2026-04-01, commit: abc1234 }
  HT-3: { status: fail, date: null, commit: null }
  # ...
level: core  # current conformance level achieved
```

Updated manually when a law transitions from fail to pass. The commit hash provides traceability.

### 3.4 Function Point Mapping and Triangulation

Each conformance law is mapped to IFPUG elementary processes before implementation begins (see Appendix A). When a law passes, its function points are counted as delivered. No backfiring. No estimation.

Additional FP from infrastructure (CI/CD, containerization, documentation systems) are counted separately using the feature/screen counting method from Paper 1.

#### 3.4.1 Three measures, triangulated

Real FP is not read off one method. The framework triangulates correctness across three mutually-confirming lenses (static check, exhaustive auto-generation, behavioral gherkin); it triangulates function points the same way, across three independent measures of delivered functionality:

- **M1: Gherkin count.** Every roled function carries exactly one gherkin (honest-gherkin-architecture.md §9). The count of passing gherkins is a direct FP count at the finest granularity. No backfiring, no estimation.
- **M2: Conformance-law / IFPUG count.** Each passing conformance law contributes the function points of the IFPUG elementary processes it maps to (Appendix A). Framework-self-conformance granularity.
- **M3: Feature/screen count.** The Paper 1 method, counted at the application surface.

The three cover overlapping but non-identical scopes, so they are never numerically identical. Velocity is tracked per measure; the discipline is to treat both their agreement and the shape of their disagreement as a signal.

#### 3.4.2 Divergence: mild is acceptable, wild is a defect signal

Let the pairwise relative divergence between any two measures, computed on their common scope and on their velocity (rate of change, not raw totals alone), be `d`.

- **Mild divergence (`d` within tolerance `T`)** is accepted and logged, not actioned. It is the expected measurement noise of differing granularity: one chain is several functions is several gherkins, but maps to fewer IFPUG elementary processes, and the feature/screen method aggregates differently again.
- **Wild divergence (`d` exceeding `T`)** halts the FP claim for that increment and triggers investigation. Its *direction* localizes the defect:
  - **M1 ≫ M2/M3** (more gherkins than laws/features account for): over-decomposition, or trivial-function inflation gaming the count, or genuine behavior not yet captured as a law or feature (a spec gap to close upward).
  - **M1 ≪ M2/M3** (fewer gherkins than laws/features claim): the dangerous case, a law or feature asserts functionality that no function specifies. A coverage gap, not noise.
  - **Levels agree but velocities diverge**: a process defect, e.g., FP being claimed faster than gherkins are authored, i.e. spec-after-the-fact.

The root cause of every wild divergence is recorded in the decision log (§3.5). `T`, and any direction-specific sub-thresholds, are calibrated in Phase 0 from the observed inter-measure variance; they are reported as a fixed parameter of the study, not tuned afterward.

### 3.5 AI Involvement Log

For the PI's Python implementation, a lightweight log captures AI involvement per activity:

```
# ~/.honest-research/ai-log.csv
date,phase,activity,ai_involvement,notes
2026-03-22,spec,conformance law HT-9 drafting,ai-assisted,Claude helped formalize the property
2026-03-23,design,persist API design,human-originated,sketched on paper first
2026-03-24,impl,classify() function,ai-generated-reviewed,Claude wrote first draft; refactored twice
```

Categories for ai_involvement:
- `human-only` — no AI tools used
- `human-originated` — human conceived; AI may have helped with syntax
- `ai-assisted` — collaborative; human directed, AI contributed substantially
- `ai-generated-reviewed` — AI produced first draft; human reviewed and modified
- `ai-generated-accepted` — AI produced; human accepted with minimal changes

This is the first dataset capturing AI involvement across the full lifecycle (ideation → specification → design → implementation → testing → refactoring).

---

## 4. Arm's-Length Team Requirements

### 4.1 License Condition

Implementations of the Honest Framework specification are licensed under [TBD] with the following research participation requirement:

1. Use the commit prefix convention (Section 3.1)
2. Maintain the conformance-status.yaml file (Section 3.3)
3. Provide monthly exports: `git log --all --numstat --format="COMMIT:%H %ad %s" --date=format:"%Y-%m-%d"`
4. Complete a brief monthly survey (5 questions, <5 minutes):
   - Team size (FTE)
   - AI tools used
   - Architectural approach (Honest Code principles followed? Which ones?)
   - Biggest technical challenge this month
   - Hours worked (approximate)

### 4.2 What Teams Receive

- Complete specification (all 12 module specs)
- Conformance suite adapted to their language's PBT framework
- Structured SDLC guidelines (from Paper 1)
- Pre-commit hook for commit prefix enforcement
- Optional: access to Python reference implementation
- Optional: architectural consultation with PI

### 4.3 What Teams Choose

- Their own architecture within language idioms
- Their own internal development practices (beyond the SDLC minimum)
- Their own AI tools
- Their own team structure

---

## 5. Relationship to Paper 1

Paper 1 (*"Process Discipline as the Key Variable"*) established process discipline as the key variable in AI-assisted enterprise development, with two supporting conditions (architectural expertise, clean codebase).

This study extends Paper 1 in four ways:

1. **Prospective design.** Paper 1 was retrospective. This study instruments from day one.
2. **Architecture as a variable.** Paper 1 held architecture constant. This study varies it across teams implementing the same spec.
3. **Real function points.** Paper 1 estimated FP via backfiring. This study counts them directly from the conformance suite.
4. **Multi-team replication.** Paper 1 used one team. This study provides replication across independent teams.

---

## 6. Expected Outputs

### 6.1 Paper 2 (Target)

Working title: *"Architecture and AI: A Prospective Multi-Language Framework Development Study"*

Expected contributions:
- First prospective study of AI-assisted framework development with instrumentation from ideation
- First direct FP measurement (no backfiring) in AI-assisted development
- Activity ratio benchmarks (spec/code/refactor) for structured AI-assisted development
- Architecture as a measurable variable (Honest Code vs. conventional, same spec, same process)
- Cross-language productivity comparison on identical functional requirements

### 6.2 Data Artifacts

- Complete git histories with semantic commit prefixes
- Session-level time logs
- AI involvement logs (PI implementation)
- Conformance tracking records
- Monthly team survey data (arm's-length teams)

---

## Appendix A: Conformance Law to Function Point Mapping

*To be completed before Phase 1 begins.*

Each conformance law will be mapped to IFPUG elementary processes:
- EI (External Input): functions that process data from outside the boundary
- EO (External Output): functions that present data with processing logic
- EQ (External Inquiry): functions that present data without processing logic
- ILF (Internal Logical File): user-maintainable data groups
- EIF (External Interface File): referenced data groups

The 50 conformance laws span 12 modules. Preliminary estimate: 150-250 FP across all laws at Full conformance level. This will be refined during Phase 0.

Where a law's elementary processes correspond to specific functions, the mapping records the gherkins those functions carry, so that the law/IFPUG count (M2) and the gherkin count (M1) are reconciled by construction at the points where their scopes coincide. The triangulation discipline (§3.4.1-3.4.2) governs the points where they do not.

---

## Appendix B: Structured SDLC Requirements (from Paper 1)

All participants must follow:
1. Written specifications before implementation
2. Conformance laws (behavioral tests) before code
3. Test-first implementation
4. Architectural review of AI-generated output
5. Pre-commit hooks (formatting, linting, commit prefix validation)
6. Automated quality pipelines

These requirements are the process discipline variable from Paper 1, held constant across all teams in this study.
