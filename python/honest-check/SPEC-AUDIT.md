# honest-check: Specification Audit Findings, Ranked by Seriousness

This document lists where honest-check's code differs from its spec, `specs/02-code-quality/honest-check-architecture.md`. I compared the spec against the code and the rule catalogue on 2026-11-11. I changed no code.

I ranked the findings by one question: does the gap let dishonest code pass the gate? To see why that question ranks them, you need to know what the gate does. honest-check runs before the framework writes a test suite for your code. It asks one thing: can a complete test suite be generated from this code? Each rule, when it fires, gives one reason the answer is no. Code that fails any rule is rejected at commit, because the framework cannot test it. The command-line run is the one the commit gate calls.

The spec defines two more ways to run the same rules: a language server for editors, and a startup check. All three run the identical rules. They differ only in how they deliver the result. So a missing rule weakens the gate, and a missing delivery surface does not.

The findings come in three tiers. Tier 1 lets dishonest code through. Tier 2 leaves the gate working but gets the documents wrong. Tier 3 is the delivery surfaces the spec describes and the code does not build.

## Tier 1: These gaps let dishonest code pass the gate.

### Finding 1: HC002 checks every link in a chain except the first one. (Resolved 2026-11-11, commit bf5922a.)

This gap is now closed. The first-link check runs in `check_references`, the whole-set pass that already reads the route map and the templates. It resolves each route's chain to its first link and checks the link's accepts against the fields the route's templates send. The rest of this finding records what was wrong before the fix.

A chain is a line of functions. Each function's output feeds the next function's input. HC002 checks that each function accepts what the function before it produces. The first function has no function before it. Its input comes from outside the program, through the templates and the routes. The spec (§4.2, derived at §497) says HC002 must check that first function's declared input against what those templates and routes actually send. The code skips that check. A comment in `rules_per_file.py` says the first link's input "is left unchecked here," because the check "needs cross-artifact inputs honest-check does not ingest yet."

That comment is out of date. honest-check now reads those inputs. The reference pass, `check_references`, reads the templates and the route map, which is the boundary data §497 asks for, and HC-REF001 already derives the route map from them. HC002 runs in the per-file pass instead, so it never sees that data. The inputs sit in the checker. HC002 is not wired to them.

This is the worst finding. HC002 looks finished, so a developer trusts it to check the whole chain. But it leaves out the first link, and the first link is where outside input enters. That input is the least trusted data in the program and the most important to check. A first function that asks for a field no template ever sends passes the gate, and the framework cannot write a test for input that never arrives. The fix no longer waits on missing inputs. The data HC002 needs is already in the checker, so the work left is to connect the first-link check to it.

### Finding 2: The spec defines HC-R006 in full, and no code runs it.

A door is a function the declaration marks as a boundary. It touches the outside world, a database, a file, or the network, and passes the value along without changing it. Changing the value is work for the pure functions, because the framework can test those. HC-R006 flags a door that changes its input instead of passing it through. Such a door hides real work behind a declaration that says it does none.

The spec gives HC-R006 a full definition (§4.2 at line 1387, listed in §8), down to the two cases it must leave alone: reading a live object like a database connection, and encoding or decoding a format like JSON. The code has no such rule, and the catalogue does not list it.

A door that reshapes its input passes the gate today. The declaration looks the same whether the body passes the value through or rebuilds it. So the lie is only in the code, and only this rule would catch it.

### Finding 3: honest-check parses six languages and checks two.

The spec describes honest-check as a checker for a mixed codebase that reads each file in its own language. The parser does handle all six languages the framework targets: Python, JavaScript, Ruby, Go, PHP, and Elixir. But the rules look for Python's syntax, and a few of them also look for JavaScript's. Only Python and JavaScript have the lists that two rules, HC-P004 and HC008, use to spot input and output. honest-check finds and parses a Ruby, Go, PHP, or Elixir file, and then almost nothing checks it, because the rules look for Python or JavaScript shapes that those files do not contain.

This is the mildest finding in this tier. The framework has no Ruby, Go, PHP, or Elixir code yet; those languages come in later phases. The hole is real against the spec's claim of six languages, but no code falls through it today. The spec admits part of this: it says no list is published for Ruby or Go yet.

## Tier 2: The gate works, but the documents are wrong.

### Finding 4: The summary table leaves out three rules the checker runs.

HC-P015, HC-P019, and HC-P020 are all in the catalogue, each is defined in §4.2, and each raises a blocking error today. The summary table in §8 lists none of them. Anyone who counts the rules from that table is short by three and never learns those three errors exist. The gate runs all three correctly. Only the summary is wrong.

### Finding 5: The command line has two flags the spec never mentions.

The code accepts `--declaration` and `--exports`. These two flags run the cross-module checks, HC-R002 through HC-R005 and HC-REF005, which compare a module's `.hd` declaration against its code. The options table in §2.1 lists neither flag. The code and the spec disagree. Either the spec should list the two flags, or the code should drop them.

## Tier 3: These delivery surfaces are unbuilt, and the gate does not need them.

### Finding 6: honest-check has no language server.

The spec (§2.2) says honest-check should run as a language server, so editors show violations as you type. It lists six features: inline warnings, automatic fixes, rule docs on hover, a list of every vocabulary, binding, and chain in the project, go-to-definition, and a `honest-check --lsp` command. The code has none of it, and there is no `--lsp` flag. The language server would run the same rules the command line already runs. So its absence costs a developer live feedback in the editor, and it costs the gate nothing.

### Finding 7: honest-check cannot fix anything it reports.

The spec lists a `--fix` flag (§2.1) that applies fixes automatically, and the language server offers the same through its code actions (§2.2). Every finding carries a `fixable` field for this. In the code, `fixable` is always `False`, there is no `--fix` flag, and nothing rewrites a file. A developer fixes each violation by hand. This costs a convenience and leaves the gate whole. Automatic fixing also deserves a hard look before anyone builds it, because a tool that rewrites honest code must not write a dishonest shape back in.

### Finding 8: honest-check does not watch files.

The spec lists a `--watch` flag (§2.1) that re-runs the checker when a file changes. The code has no such flag and watches nothing. A developer re-runs the checker by hand. The gate does not need it.

## A finding I took back

My first pass flagged HC-SM06 as a rule the spec defines and the code skips. That was wrong. The spec (line 1982) says HC-SM06 was withdrawn. It assumed a state machine is a set of fields and a transition writes them. The framework's real model makes a state a single name and a transition a pure lookup that writes nothing. The rule described a model the framework threw out, so no code should run it. The spec and the catalogue agree it should not exist.

## What I did not check

I did not compare each rule's exact behavior against its spec text. I checked that a rule exists, runs, and has a test. I did not check that it catches the exact cases the spec names and nothing else. I also did not check the four output formats (§6), the suppression rules (§7) in detail, or the discovery and extraction steps (§3.3 through §3.5). A problem could still sit inside a rule that this pass did not open.
