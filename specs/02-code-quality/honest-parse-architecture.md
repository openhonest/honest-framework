# honest-parse: Architecture Specification

honest-parse is the framework's only parser. Every other module reaches a syntax tree through this one, and no module reaches tree-sitter directly. One module owning the parse means one place to add a grammar, one place where the outside world is touched, and one shape for every language the framework reads: Python, JavaScript, Ruby, PHP, Go, Elixir, HTML, Jinja, CSS and `.hd`.

It is the one true leaf. It depends on nothing in the framework, it is written and hand-checked before honest-check exists, and the whole gate stands on it (see the framework spec, *The build order*).

## Where grammar selection and parsing happen

All three entry paths use the same grammar table and the same reader.

**One reader.** `read_tree(source, grammar)` is the only function that calls tree-sitter. It takes source bytes and a resolved grammar handle, creates a parser for the call, and returns the tree with any recovery nodes intact.

**The grammar-directed door.** `parse(source, language)` hands the bytes and explicit grammar name to `read_by_language`. The orchestrator asks `grammar_for` to look up the name in the immutable grammar table. A recognized name supplies the handle to `read_tree`. An unsupported name returns the existing `unknown_grammar` server fault with the requested name and a sorted list of the supported names. The orchestrator returns that fault unchanged without calling the reader.

**One chooser.** `language_of(path)` is pure and answers which grammar a path is read under, from a table of extensions written down in full. The table is closed: an extension absent from it is a named failure, not a fall-back to the commonest language. A fall-back would read a Ruby file under the Python grammar and report a clean parse, so the file would pass every rule that reads its tree while nothing had actually read the file.

This table belongs here because the pairing of an extension with a grammar is this module's own vocabulary. Any module that keeps its own copy has a second answer to one question, and the two drift.

**The path-directed door.** `parse_source(source, path)` hands off to `place_source`. That orchestrator finds the language through `language_of`, resolves its handle with `grammar_for`, and asks `read_tree` for the tree. It returns a lookup fault unchanged or passes the tree to `_checked_tree`. That helper wraps a clean tree or calls `_syntax_error` to report the path, grammar, and one-based location of the first ERROR or MISSING node.

**The pure helpers.** `node_text`, `line_col`, `walk` and `first_error_node` compute over a tree and touch nothing. `first_error_node` calls `walk`; the declaration says so.

## Grammar-directed root inspection

`parse_root_node(source, language)` accepts source bytes and an explicit grammar name and hands both to `read_root_node`. The orchestrator resolves the grammar with `grammar_for` and returns an unknown-grammar fault unchanged if the lookup fails. For a resolved grammar, it asks the same `read_tree` reader for the tree and passes the result to `root_node_or_fault` for inspection.

A recognized grammar returns the actual tree-sitter root even when it has ERROR or MISSING descendants. This lets a test-body scan inspect statements the parser recovered, while the mutation engine can apply its own failure contract to an erroneous root. The path-directed door continues to reject syntax errors with a location.

## No per-language functions

Ten functions named `parse_python`, `parse_javascript` and so on are ten names for one call with a different constant. They are the if/elif of a module surface: each one is an arm of a choice that a table makes in one line, and ten of them turn one reader into ten doors in the picture, which is what the four-column model exists to show. A caller that knows its language passes the language. A caller that does not passes the path.

## What the declaration must say

The `.hd` is this module's statement of the above, and it resolves against the code or it is false (`HC-REF005`). Three things it must carry that an earlier version did not:

- **Every call, written down.** The three doors name their respective orchestrators. Each orchestrator names the shared `read_tree` reader and the helpers it uses. `first_error_node` calls `walk`. HC-R002 checks the direction of the arrows by reading the declared calls, so a module that declares none passes that rule without a single check running.
- **An `outputs` line, even when it is empty.** This module reads and never writes, so its outputs are nothing, and nothing is stated rather than left out. Silence and nothing are different facts, and a check that asks only whether one of `inputs` or `outputs` is present reads the first as the second.
- **A return type that matches.** `line_col` answers a `Position` of line and column, each counted from one. `first_error_node` answers the first error node **or nothing**, so the declaration says so rather than promising a node it does not always have.

## Grammars

A language the framework reads needs its grammar in this module before any rule can check that language, and a reference kind cannot be checked before its grammar is here. That covers more than the programming languages: the template and style grammars are what let the checker resolve a template's `hx-get` to a route, or a `class` to a stylesheet rule.

## Verification

The module is hand-checked first, against the parser rules, because the gate that would check it is built on top of it: a node's text is exactly the slice of source it covers; the walk visits every node, parents before children; line and column count from one; it reports an error exactly when the tree has one; the same input gives the same result; only known languages are accepted; and text decodes correctly. Once honest-check exists, honest-parse re-enters through the same gate as every other module.
