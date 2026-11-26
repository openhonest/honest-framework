Feature: honest-parse — the shared parsing boundary
  One scenario per function. One function touches tree-sitter, one chooses the grammar from a
  path, one orchestrates the two, and the rest compute over the tree.

  # hd: python/honest-parse/honest-parse.hd::parse_root_node
  Scenario: parse_root_node returns the root for the explicit grammar
    Given source: bytes holds valid Python source and language: str is "python"
    When parse_root_node is called
    Then it returns the Python syntax tree root Node

  # hd: python/honest-parse/honest-parse.hd::parse_root_node
  Scenario: parse_root_node preserves recovery nodes for malformed source
    Given source: bytes holds malformed Python source with parser recovery descendants and language: str is "python"
    When parse_root_node is called
    Then it returns the recovered root Node with its ERROR or MISSING descendants retained

  # hd: python/honest-parse/honest-parse.hd::parse_root_node
  Scenario: parse_root_node returns the unknown grammar fault
    Given source: bytes holds source to inspect and language: str is not a known grammar name
    When parse_root_node is called
    Then it returns an unknown_grammar Fault

  # hd: python/honest-parse/honest-parse.hd::read_root_node
  Scenario: read_root_node returns the recovered root for the requested grammar
    Given source: bytes holds malformed Python source with parser recovery descendants and language: str is "python"
    When read_root_node is called
    Then it returns the root produced by the shared parser for those exact bytes and grammar, retaining the recovery descendants

  # hd: python/honest-parse/honest-parse.hd::read_root_node
  Scenario: read_root_node returns the fault for an unknown grammar
    Given source: bytes holds source to inspect and language: str is not a known grammar name
    When read_root_node is called
    Then it returns the unknown_grammar Fault

  # hd: python/honest-parse/honest-parse.hd::root_node_or_fault
  Scenario: root_node_or_fault returns the actual tree root
    Given result: Tree | Fault is a successfully parsed Tree
    When root_node_or_fault is called
    Then it returns that Tree’s actual root Node

  # hd: python/honest-parse/honest-parse.hd::root_node_or_fault
  Scenario: root_node_or_fault preserves recovery descendants
    Given result: Tree | Fault is a recovered Tree with ERROR or MISSING descendants
    When root_node_or_fault is called
    Then it returns that Tree’s actual root with those descendants retained

  # hd: python/honest-parse/honest-parse.hd::root_node_or_fault
  Scenario: root_node_or_fault passes through the unknown grammar fault
    Given result: Tree | Fault is an unknown_grammar Fault
    When root_node_or_fault is called
    Then it returns that same Fault unchanged

  # hd: python/honest-parse/honest-parse.hd::read_by_language
  Scenario: read_by_language returns the original recovered tree
    Given source: bytes holds malformed Python source and language: str is "python"
    When read_by_language is called
    Then it returns the actual Tree produced with the Python grammar and retains its recovery nodes

  # hd: python/honest-parse/honest-parse.hd::read_by_language
  Scenario: read_by_language returns the missing grammar fault
    Given source: bytes holds source to parse and language: str names an unsupported grammar
    When read_by_language is called
    Then it passes through the unknown_grammar fault without asking the tree reader for a parse

  # hd: python/honest-parse/honest-parse.hd::grammar_for
  Scenario: grammar_for returns the known grammar handle
    Given language: str names a grammar in the immutable table
    When grammar_for is called
    Then it returns the matched GrammarHandle

  # hd: python/honest-parse/honest-parse.hd::grammar_for
  Scenario: grammar_for returns a fault for a missing grammar
    Given language: str names no grammar in the immutable table
    When grammar_for is called
    Then it returns an unknown_grammar fault

  # hd: python/honest-parse/honest-parse.hd::read_tree
  Scenario: read_tree parses the bytes using the resolved grammar
    Given source: bytes contains Python source and grammar: GrammarHandle is the resolved Python grammar
    When read_tree is called
    Then it parses those bytes with a new parser using that grammar and returns the resulting Tree

  # hd: python/honest-parse/honest-parse.hd::_pick
  Scenario: _pick invokes only the thunk selected by truthiness
    Given flag: any is truthy or falsy, and when_true: Callable and when_false: Callable are zero-argument operations with distinct answers
    When _pick is called
    Then it invokes when_true once for a truthy flag or when_false once for a falsy flag, leaves the other operation uncalled, and returns the selected operation’s exact answer

  # hd: python/honest-parse/honest-parse.hd::_unknown_grammar
  Scenario: _unknown_grammar reports the request and sorted supported names
    Given language: str is an unsupported grammar name
    When _unknown_grammar is called
    Then it returns an unknown_grammar server fault whose message contains the requested name and the supported names in sorted order

  # hd: python/honest-parse/honest-parse.hd::_checked_tree
  Scenario: _checked_tree wraps the original clean tree
    Given tree: Tree has no syntax error, path: str names its source file, and language: str names its grammar
    When _checked_tree is called
    Then it returns the original tree in the ok arm

  # hd: python/honest-parse/honest-parse.hd::_checked_tree
  Scenario: _checked_tree returns a located fault for a recovered tree
    Given tree: Tree contains a syntax error, path: str names its source file, and language: str names its grammar
    When _checked_tree is called
    Then it returns the located syntax_error fault for that path and grammar

  # hd: python/honest-parse/honest-parse.hd::_syntax_error
  Scenario: _syntax_error reports the first recovery node location
    Given root: Node contains an ERROR or MISSING node, path: str is "broken.py", and language: str is "python"
    When _syntax_error is called
    Then it returns a syntax_error client fault whose message names the path, grammar and one-based line and column of the first ERROR or MISSING node, and whose detail carries path, line and col

  Scenario: parse turns source into a syntax tree
    Given source text and the name of a supported language
    When parse reads it
    Then it returns the syntax tree for that source
    But a grammar this module does not carry is refused by name, saying which grammars it has

  Scenario: language_of names the grammar a path is read under
    Given a file path
    When language_of reads its extension
    Then it returns the grammar declared for that extension
    But an extension the table does not carry is refused, never read as the commonest grammar

  Scenario: place_source reads source under the grammar its path names
    Given source text and the path it came from
    When place_source asks which grammar the path names and reads the source under it
    Then it returns the syntax tree for that grammar
    But a path it cannot place is refused and the source is never read
    And source that does not parse is refused with a fault naming the line and column of the error

  Scenario: parse_source hands a calling module's call to the orchestrator
    Given a calling module with source text and the path it came from
    When parse_source receives the call
    Then it hands the call to the orchestrator and returns that answer unchanged


  Scenario: line_col reports a node's start position, counting from one
    Given a node
    When line_col reads its start
    Then it returns the line and column, each counted from one

  Scenario: walk returns every node, parents before children
    Given the root of a tree
    When walk traverses it
    Then it returns a list of every node in the subtree, each parent before its children
    But it answers a list, not a stream, so a second reader sees the same nodes

  Scenario: first_error_node finds the first broken place in a tree
    Given the root of a tree
    When first_error_node scans it
    Then it returns the first error or missing node, or nothing when the tree is clean
