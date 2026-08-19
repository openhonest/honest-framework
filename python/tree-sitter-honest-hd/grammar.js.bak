/// Honest Framework `.hd` architecture-declaration grammar, owned by honest-parse.
///
/// `.hd` states a module's architecture as data (spec:
/// specs/02-code-quality/honest-design-architecture.md). This grammar parses both file kinds:
/// module files (`module <name>` followed by its declarations) and workspace files (`rule` /
/// `actor` / `flow`). Indentation is NOT significant — whitespace and `#` comments are extras —
/// so a declaration is recognised by its leading keyword, not its column, exactly as the real
/// corpus is written. honest-parse exposes this as the `hd` grammar; honest-design's reader folds
/// the resulting tree into the IR.
///
/// No keyword extraction (`word:`) on purpose: the corpus uses keyword-shaped names as ordinary
/// identifiers — a function named `on` (honest-state), `set` as both the set-declaration keyword and
/// the `set<...>` generic type. tree-sitter's context-aware lexer admits a keyword only where the
/// grammar expects it, so these coexist without a reserved-word clash.

const commaSep1 = (rule) => seq(rule, repeat(seq(',', rule)));
const commaSep = (rule) => optional(commaSep1(rule));

module.exports = grammar({
  name: 'honest_hd',

  extras: $ => [/\s+/, $.comment],

  rules: {
    source_file: $ => repeat($._top_decl),

    _top_decl: $ => choice(
      $.module_decl,
      $.rule_decl,
      $.actor_decl,
      $.flow_decl,
    ),

    // --- Module and its body -------------------------------------------------

    module_decl: $ => seq('module', field('name', $.identifier), repeat($._body_decl)),

    _body_decl: $ => choice(
      $.layer_decl,
      $.type_decl,
      $.set_decl,
      $.vocabulary_decl,
      $.dispatch_decl,
      $.example_decl,
      $.function_decl,
      $.chain_decl,
      $.route_decl,
      $.entry_decl,
      $.html_attr_decl,
    ),

    layer_decl: $ => seq('layer', field('name', $.identifier)),

    // --- Types ---------------------------------------------------------------

    type_decl: $ => seq('type', field('name', $.identifier), '=', field('value', $._type_expr)),

    _type_expr: $ => choice($.record_type, $.type),

    record_type: $ => seq('{', repeat($.field), '}'),

    field: $ => seq(field('name', $.identifier), ':', field('type', $.type)),

    // A type is a union of one or more atoms (`Manifest | Fault`). An atom is a name (str, int,
    // Vocabulary, set, ...) with optional generic arguments; generics nest (dict<str, set<str>>).
    // `set` reaches here as an ordinary identifier.
    type: $ => seq($.type_atom, repeat(seq('|', $.type_atom))),

    type_atom: $ => seq(field('name', $.identifier), optional($.generic_args)),

    generic_args: $ => seq('<', commaSep1($.type), '>'),

    // --- Sets and vocabularies ----------------------------------------------

    set_decl: $ => seq('set', field('name', $.identifier), '=', '{', commaSep($.set_member), '}'),

    set_member: $ => seq(field('value', $.string), optional(seq(':', field('description', $.string)))),

    vocabulary_decl: $ => seq('vocabulary', field('name', $.identifier), '=', '{', commaSep($.identifier), '}'),

    // --- Dispatch tables -----------------------------------------------------

    dispatch_decl: $ => seq('dispatch', field('name', $.identifier), '=', '{', commaSep($.dispatch_entry), '}'),

    dispatch_entry: $ => seq(field('key', $.string), '->', field('handler', $.identifier)),

    // --- Examples (living spec) ---------------------------------------------

    example_decl: $ => seq('example', field('name', $.identifier), 'of', field('chain', $.identifier), '=', field('text', $.string)),

    // --- Functions (the four columns) ---------------------------------------

    function_decl: $ => seq(
      optional(field('role', $.role)),
      'fn',
      field('name', $.identifier),
      $.signature,
      repeat($._annotation),
    ),

    role: $ => choice('boundary_in', 'boundary_out', 'orchestrator'),

    signature: $ => seq(':', $.params, '->', field('ret', $.type)),

    params: $ => seq('(', commaSep($.param), ')'),

    param: $ => seq(field('name', $.identifier), ':', field('type', $.type)),

    _annotation: $ => choice($.invokes, $.raises, $.side_effect),

    invokes: $ => seq('invokes', commaSep1($.identifier)),

    // Fault codes are written bare (no_transition) or quoted ("alert.delivery_failed").
    raises: $ => seq('raises', commaSep1(choice($.identifier, $.string))),

    side_effect: $ => seq('side_effect', field('direction', choice('reads', 'writes', 'reads_writes')), field('target', $.string)),

    // --- Chains --------------------------------------------------------------

    chain_decl: $ => seq('chain', field('name', $.identifier), '=', $.chain_body),

    chain_body: $ => seq($.identifier, repeat(seq('->', $.identifier))),

    // --- Routes and declared client attributes -------------------------------

    route_decl: $ => seq('route', field('path', $.string), '->', field('target', $.identifier)),

    // An entry point whose call-site shape is described by a string (a decorator, a context
    // manager, a middleware registration), dispatching to a function.
    entry_decl: $ => seq('entry', field('callsite', $.string), '->', field('target', $.identifier)),

    html_attr_decl: $ => seq('html_attr', field('attr', $.string), field('description', $.string)),

    // --- Workspace files -----------------------------------------------------

    rule_decl: $ => seq('rule', field('id', $.identifier), optional(seq('on', field('module', $.identifier))), '=', field('statement', $.string)),

    actor_decl: $ => seq('actor', field('name', $.identifier)),

    flow_decl: $ => seq('flow', field('name', $.identifier), 'in', field('group', $.identifier), '=', $.flow_body),

    flow_body: $ => seq($.identifier, repeat(seq('->', $.identifier))),

    // --- Terminals -----------------------------------------------------------

    // Identifiers admit internal hyphens (honest-page, HC-P001) but never a trailing one, so `->`
    // is always the arrow token, never part of a name.
    identifier: $ => token(/[a-zA-Z_][a-zA-Z0-9_]*(-[a-zA-Z0-9_]+)*/),

    string: $ => token(choice(/"([^"\\]|\\.)*"/, /'([^'\\]|\\.)*'/)),

    comment: $ => token(seq('#', /[^\n]*/)),
  }
});
