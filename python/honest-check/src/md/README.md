# honest-check — intent notes

honest-check is the static checker that enforces the Honest Code principles, and it is one of the two modules that are also the toolchain. It parses source with tree-sitter and reports violations as diagnostics. It never runs the code it checks. Every rule cites the spec rule it implements.

These notes record why the code is shaped the way it is. They are the public half of that record: the formal contract lives in `specs/02-code-quality/honest-check-architecture.md`, and the working session notes live in the gitignored `.agents.md`. A note here is something we chose to publish for a reader, human or agent, who needs the reasoning and not just the rules.

## Key subtleties

A diagnostic carries a severity, and only an error blocks a commit. A warning and an info report and let the commit through. A rule lands as a warning when the codebase does not yet obey it, and is promoted to an error once the code is clean.

The rule catalogue is `specs/rules.json`, and it is the single list of every rule. The spec tables and the code must both agree with it, and `rules-check.py` fails the build when they drift. A rule the code emits but the catalogue does not name is undeclared; a rule the catalogue names but the code never emits is a phantom. Both are caught.

An adoption level is a named, closed set of rules a codebase declares it holds. `adoption.py` defines the levels. A rule not placed in any level still runs, but reports as info and blocks nothing, so a rule meant to have teeth must be placed.

Every rule honest-check emits, honest-check's own code must pass. The module checks itself.

## File Index

- [adding-a-rule.md](adding-a-rule.md) — the four places a new rule must be registered, and the order to build it in. Read this before adding a rule; three of the four are easy to forget and a gate catches each.
