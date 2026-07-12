# tree-sitter-honest-jinja

A minimal Jinja **statement** grammar for tree-sitter, owned by honest-parse. It is not a full Jinja
expression grammar: it recognises the delimiters (`{% .. %}`, `{{ .. }}`, `{# .. #}`) and, inside a
statement, the tag keyword (`tag` field) and any string-literal arguments (`string` nodes). Tag
interiors and HTML are opaque `template_data`. The purpose is to let honest-check resolve
`{% include %}` / `{% extends %}` targets (HC-REF002): a literal target is a `string` child of the
statement; a dynamic one has none. It parses real templates with zero ERROR nodes.

`src/parser.c` is generated from `grammar.js` (`tree-sitter generate --abi 14`) and committed so the
package builds without the tree-sitter CLI. Regenerate only when `grammar.js` changes.
