/// Honest Framework template grammar (Jinja statement subset).
///
/// Purpose: let honest-parse expose {% include %} / {% extends %} targets so honest-check can
/// resolve them (HC-REF002). It recognises the Jinja delimiters — statements {% .. %}, output
/// {{ .. }}, comments {# .. #} — and, inside a statement, the tag keyword (`tag` field) and any
/// string-literal arguments (`string` nodes).
///
/// The interior of a tag is otherwise OPAQUE: after the tag keyword a statement is a sequence of
/// string literals and `_stmt_text` (any run that is neither a string nor the closing `%}`), and an
/// output `{{ .. }}` is strings and `_out_text` (neither a string nor `}}`). This deliberately does
/// not model Jinja expressions — filters, dict/set literals, arithmetic, comparisons — because the
/// checker needs only the tag keyword and its string arguments, and an opaque interior parses every
/// real expression with zero ERROR nodes instead of failing on unenumerated syntax. A literal target
/// appears as a `string` child of an include/extends statement; a dynamic one has no string child.
module.exports = grammar({
  name: 'honest_jinja',

  extras: $ => [/\s+/],

  rules: {
    template: $ => repeat($._node),

    _node: $ => choice($.statement, $.output, $.comment, $.template_data),

    statement: $ => seq(
      choice('{%', '{%-'),
      field('tag', $.identifier),
      repeat(choice($.string, $._stmt_text)),
      choice('%}', '-%}'),
    ),

    output: $ => seq(
      choice('{{', '{{-'),
      repeat(choice($.string, $._out_text)),
      choice('}}', '-}}'),
    ),

    comment: $ => seq('{#', optional($._comment_body), '#}'),

    string: $ => token(choice(/"([^"\\]|\\.)*"/, /'([^'\\]|\\.)*'/)),

    identifier: $ => token(/[a-zA-Z_][a-zA-Z0-9_]*/),

    // Statement interior: anything that is not a string start and not the `%}` close. `{` is excluded
    // from the run and re-admitted as a lone alternative (like template_data) because tree-sitter will
    // not start a regex token with a bare `{` — it is the delimiter-start char. This lets dict/set
    // literals inside a tag parse as opaque text rather than ERROR.
    _stmt_text: $ => token(prec(-1, /([^"'%{]|%[^}]|\{)+/)),

    // Output interior: anything that is not a string start and not the `}}` close (same `{` handling).
    _out_text: $ => token(prec(-1, /([^"'}{]|}[^}]|\{)+/)),

    // Comment interior: anything that is not the `#}` close.
    _comment_body: $ => token(prec(-1, /([^#]|#[^}])+/)),

    // Raw template text between delimiters: runs of non-brace, or a lone brace.
    template_data: $ => token(prec(-1, /[^{]+|\{/)),
  }
});
