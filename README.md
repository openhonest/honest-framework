# Honest Framework

Language-agnostic framework specification for code that is correct by design. The structural-correctness side of the Open Honest Foundation's three-standard portfolio.

## What's here

- `specs/` — Honest Framework specifications, tiered:
  - `specs/01-framework/` — core framework spec + conformance suite
  - `specs/02-code-quality/` — code-quality dimension
  - `specs/03-application-production/` — application-production dimension
- `articles/` — three canonical articles (honest-advantages, honest-testing, honest-type-magic)
- `principles/` — foundational philosophy
  - `poka-yoke.md` — velocity-multiplier manifesto: which categories of bug each design decision eliminates structurally
  - `honest-code-principles.md` — sixteen Honest Code practices
- `methodology/` — verification approach
  - `contract-testing.md` — user-journey-to-function contract mapping methodology
- `python/` — Python reference implementation (in active development)
- `javascript/`, `ruby/` — placeholders for additional language implementations
- `integration-test-challenge.md` — public unbreakable-todo-app challenge (a marketing activity for the framework whose results feed back into research)
- `INSTRUMENT_CONE_SYNTHESIS.md` — epistemic anchor: the instrument defines what is visible. A reminder that current code-quality metrics can't find what they aren't looking for; the framework's value is partly about expanding the cone of what's visible.
- `analyst-strategy-handoff.md` — industry analyst landscape positioning
- `.githooks/commit-msg` — pre-commit hook enforcing commit-message prefixes for research instrumentation. Install with `git config core.hooksPath .githooks`.

The architectural-diagram renderer (honest-design) is proprietary and lives at `~/dev/commercial-honest/copyright/software/explorer/`; rendered output for FOSS modules is published at `~/dev/open-honest/honestframework-website/explorer/`. The `ui-audit` reference tool lives at `~/dev/open-honest/slop-audit/tools/ui-audit/` since it instruments one aspect of Slop Audit dimension 4.18.

## Companion standards under the Foundation

- [Slop Audit](https://github.com/openhonest/slop-audit) — measurement instrument for software quality
- [MÉTRON Framework](https://github.com/openhonest/metron-framework) — model family for cross-linguistic AI research (forthcoming)
- [Honest Pen-Test](https://github.com/openhonest/honest-pentest) — symmetric counterpart to the Slop Audit (license pending)

## Documentation site

The persona-aware reading guide lives at [honestframework.software](https://honestframework.software) (source: [openhonest/honestframework-website](https://github.com/openhonest/honestframework-website)).

## License

- Code: Apache-2.0
- Documentation content: CC-BY-NC-4.0

Foundation-governed; in formation. Will be flipped public when the Foundation incorporates and the framework reaches v1 reference implementation.
