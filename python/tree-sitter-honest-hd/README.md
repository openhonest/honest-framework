# tree-sitter-honest-hd

The `.hd` architecture-declaration grammar for tree-sitter, owned by honest-parse. It parses both
`.hd` file kinds — module files (`module` + declarations) and workspace files (`rule` / `actor` /
`flow`) — surfacing modules, layers, types, sets, vocabularies, dispatch tables, examples, the four
function roles (`boundary_in` / `orchestrator` / `fn` / `boundary_out`) with their signatures,
`side_effect`s, `invokes`, and `raises`, chains, routes, and `html_attr`s. Indentation is not
significant; `#` comments and whitespace are extras. honest-design's reader folds the tree into the
language-agnostic IR (spec: `specs/02-code-quality/honest-design-architecture.md`).

`src/parser.c` is generated from `grammar.js` (`tree-sitter generate --abi 14`) and committed so the
package builds without the tree-sitter CLI. Regenerate only when `grammar.js` changes.
