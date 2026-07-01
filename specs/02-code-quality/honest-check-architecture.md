# honest-check: Architecture Specification

**Version:** 0.1 (Draft)
**Date:** March 15, 2026
**Status:** Active
**Author:** Adam Zachary Wasserman

---

## 1. Purpose and Scope

honest-check is the **pre-auto-generation** verification layer of the Honest Framework. It answers a single operational question:

> *Can the complete auto-generated test suite be generated from this code's declarations?*

If yes — the code is honest. Auto-generation proceeds; honest-test runs the generated suite. If no — the code is **dishonest**. No test suite can be generated, so no testing can occur, so no shipping can occur. The code is rejected at the pre-commit boundary.

Every HC rule is a precondition for auto-generation. Each rule, when it fires, names one reason auto-generation cannot produce a complete suite:

| Rule family | What auto-generation cannot do when the rule fires |
|---|---|
| HC001, HC002 | Cannot generate chain contract tests — vocabulary missing or incompatible |
| HC003, HC011 | Cannot generate unambiguous classification — recognizers overlap or are catch-all |
| HC006, HC007 | Cannot generate composed-type or chain tests — references unresolved or chain empty |
| HC-SM01/02/05 | Cannot generate exhaustive state machine tests — state/event space incomplete |
| HC-P001 | Cannot enumerate dispatch paths — branches are not data |
| HC-P003, HC-P010 | Cannot verify purity — no classes (inheritance), non-serializable data |
| HC-P002 | Cannot verify the caught path — catching in business logic hides faults from the manifest |
| HC-P004, HC008 | Cannot verify boundary isolation — I/O outside declared boundaries |
| HC-P013 | Cannot enumerate the routing key's value space — a predicate behind a database routing key is unbounded |
| HC-P014 | Cannot distinguish slots — recognizer reuse collapses semantic roles |
| HC-P016 | Cannot verify purity — closure carries mutable state |
| HC-P017 | Cannot generate serialization tests — HTTP output function has no declared vocabulary |
| HC-R001 | Cannot reach every function — orphan function has no declared role |

**honest-check is a linter only in mechanism.** In purpose, it is the gate between dishonest code and the auto-generation pipeline. Code that passes honest-check is guaranteed to have a complete auto-generated test suite. Code that fails has no test story at all.

It reads source files, resolves aliases, walks abstract syntax trees, and reports violations. It never executes application code. It never modifies files. It produces a report. Its exit code is the signal to CI: 0 = generatable, 1 = dishonest, 2 = internal failure.

**Boundary to honest-test.** honest-check asks whether auto-generation *can* run; honest-test asks whether the generated suite *passes*. Rules that can be verified by reading code belong here. Rules that require running the generated code belong in honest-test. When a rule cannot be verified statically but an analog exists at runtime, honest-check emits an `info` diagnostic directing the developer to the corresponding honest-test check.

### 1.1 Relationship to Other Specs

The rule algorithms in this document were originally specified in `honest-type-architecture.md` sections 12 and 13. That document now defers to this one as the canonical reference for all HC rules. `honest-type-architecture.md` retains its own construction-time validation (reserved word checks, vocabulary overlap) as first-class behavior of the `vocabulary()` constructor — those are not honest-check rules, they are runtime errors that happen to fire at construction time.

### 1.2 What honest-check Covers

- Honest Framework structural rules: vocabularies, bindings, links, chains, composed types, state machines
- Honest Code principle rules: the architectural positions from `honest-code-principles.md` that are statically verifiable
- Cross-language minimum rules: a language-agnostic core that every implementation must support
- Language-specific guidance: how each rule manifests in each target language

### 1.3 What honest-check Does Not Cover

- Runtime behavior: correctness of business logic, purity verification, idempotency — these belong in honest-test
- Performance: profiling, benchmarking, runtime measurement
- Security: authentication, authorization, cryptographic correctness — these belong in honest-auth
- Style: formatting, naming conventions, line length — use language-native formatters

---

## 2. Invocation Surfaces

honest-check has three invocation surfaces. The rule set is identical across all three. The delivery mechanism differs.

### 2.1 CLI

The primary invocation surface. Every language implementation must support CLI invocation.

```
honest-check [options] [paths...]
```

**Options:**

| Flag | Description |
|---|---|
| `--config` | Path to `honest-check.toml` (default: nearest ancestor directory) |
| `--format` | Output format: `human` (default), `json`, `github`, `junit` |
| `--severity` | Minimum severity to report: `error`, `warning`, `info` (default: `warning`) |
| `--fix` | Apply auto-fixable corrections (conservative subset only) |
| `--watch` | Re-run on file change |
| `--rule` | Run only the specified rule(s): `--rule HC001 --rule HC-P002` |
| `--no-rule` | Suppress specific rule(s) |

**Exit codes:**

| Code | Meaning |
|---|---|
| 0 | No errors (warnings may be present) |
| 1 | One or more errors |
| 2 | Configuration error or honest-check internal failure |

**Pre-commit hook example (Python):**

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: honest-check
        name: honest-check
        entry: honest-check
        language: system
        types: [python]
        pass_filenames: false
        args: [src/]
```

**CI example (GitHub Actions):**

```yaml
- name: honest-check
  run: honest-check --format github src/
```

### 2.2 Language Server Protocol (LSP)

honest-check implements the Language Server Protocol to provide real-time diagnostics in editors that support LSP (VS Code, Neovim, Emacs, JetBrains IDEs).

**Capabilities:**

| LSP Capability | honest-check support |
|---|---|
| `textDocument/publishDiagnostics` | All HC rules as inline diagnostics |
| `textDocument/codeAction` | Auto-fix actions for fixable rules |
| `textDocument/hover` | Rule documentation on hover over a violation |
| `workspace/symbol` | All declared vocabularies, bindings, chains |
| `textDocument/definition` | Go-to-definition for vocabulary types and chain links |

**LSP server startup:**

```
honest-check --lsp
```

The LSP server reads stdin/stdout using the JSON-RPC 2.0 protocol. Configuration is read from `honest-check.toml` in the workspace root.

**Editor integration notes:**

In LSP mode, honest-check re-runs affected rules incrementally on each file save. Construction-time rules (HC003, HC006, HC011) re-run when any vocabulary definition file changes. Chain rules (HC001, HC002, HC007) re-run when any chain or link definition file changes.

### 2.3 Framework Startup Integration

In development mode, honest-check runs at application startup. If violations are found, the application reports them in the terminal and optionally refuses to start.

**Python example:**

```python
# app.py
from honest_check import startup_check

app = FastAPI()

if settings.ENV == "development":
    startup_check(
        paths=["src/"],
        on_error="warn",      # "warn" | "raise" | "halt"
        severity="error",     # only errors block startup
    )
```

**Startup check behavior:**

| `on_error` value | Behavior on errors |
|---|---|
| `warn` | Print violations to stderr, continue startup |
| `raise` | Raise `HonestCheckError` with full report |
| `halt` | Print violations and exit process with code 1 |

Startup integration runs only construction-time and static analysis rules. It does not run rules that require full AST analysis of the entire codebase, as those are too slow for startup. The subset that runs at startup is declared in each rule's metadata as `startup: true/false`.

**Startup-eligible rules:** HC001, HC002, HC003, HC006, HC007, HC011, HC-SM01, HC-SM02, HC-SM05.

---

## 3. Discovery and AST Analysis

### 3.1 Configuration

honest-check reads `honest-check.toml` from the nearest ancestor directory, or from the path specified by `--config`.

```toml
# honest-check.toml

[check]
paths = ["src/pipelines/", "src/vocab/", "src/state/"]
exclude = ["src/migrations/", "**/__pycache__/"]
severity = "warning"

[rules]
# Suppress specific rules globally
disable = ["HC-P006"]

# Per-path rule configuration
[rules.HC-P008]
max_lines = 15    # override default of 10

[rules.HC-P012]
max_mocks = 3     # override default of 2

[startup]
on_error = "warn"
```

### 3.2 File Discovery

```
FUNCTION discover_files(paths, exclude, language):
    files ← []

    FOR EACH path IN paths:
        IF path is a file:
            IF NOT matches_any(path, exclude):
                APPEND path TO files
        IF path is a directory:
            FOR EACH file IN recursive_walk(path):
                IF file.extension IN language_extensions(language):
                    IF NOT matches_any(file, exclude):
                        APPEND file TO files

    RETURN files
```

Language extensions by implementation:

| Language | Extensions |
|---|---|
| Python | `.py` |
| JavaScript/TypeScript | `.js`, `.ts`, `.mjs`, `.cjs` |
| Ruby | `.rb` |
| Go | `.go` |

### 3.3 AST Alias Resolution

honest-check must resolve import aliases to identify honest-framework calls regardless of how they are imported.

```
FUNCTION resolve_aliases(ast):
    aliases ← {}

    FOR EACH import_statement IN ast:
        // Python: from honest_type import vocabulary as v
        IF import_statement is "from honest_type import X as Y":
            aliases[Y] ← X

        // Python: import honest_type as ht
        IF import_statement is "import honest_type as Z":
            aliases[Z + ".*"] ← "honest_type.*"

        // JavaScript: import { vocabulary as v } from 'honest-type'
        IF import_statement is "import { X as Y } from 'honest-type'":
            aliases[Y] ← X

        // JavaScript: import * as ht from 'honest-type'
        IF import_statement is "import * as Z from 'honest-type'":
            aliases[Z + ".*"] ← "honest_type.*"

    RETURN aliases

FUNCTION is_honest_call(node, name, aliases):
    IF node.func.name = name:
        RETURN true
    IF node.func.name IN aliases AND aliases[node.func.name] = name:
        RETURN true
    RETURN false
```

### 3.4 Declaration Graph

After alias resolution, honest-check builds a declaration graph:

```
declaration_graph = {
    vocabularies: { name → vocabulary_def },
    bindings:     { name → binding_def },
    links:        { name → link_def },
    chains:       { name → chain_def },
    state_machines: { name → state_machine_def },
}
```

Rules operate on this graph, not on raw ASTs. This separates parsing concerns from rule logic.

---

## 4. Rules by Firing Time

Rules are organized by when they fire. Every rule fires in CLI mode. The `startup` column indicates whether the rule fires in framework startup integration. The `lsp` column indicates whether the rule provides real-time LSP diagnostics.

### 4.1 Construction Time

These rules fire when honest-framework objects are constructed: `vocabulary()`, `binding()`, `chain()`, `composed()`, `state_machine()`. In CLI and LSP mode, honest-check simulates construction by analyzing the call sites. In startup mode, actual construction fires these checks.

| Rule | Severity | Startup | LSP | Description |
|---|---|---|---|---|
| HC003 | Error/Warning | ✓ | ✓ | Recognizer overlap within a vocabulary |
| HC006 | Error | ✓ | ✓ | Composed type references unknown base type |
| HC007 | Error | ✓ | ✓ | Empty chain |
| HC011 | Error | ✓ | ✓ | Catch-all recognizer |
| HC-SM01 | Error | ✓ | ✓ | State not in vocabulary |
| HC-SM02 | Error | ✓ | ✓ | Event not in vocabulary |
| HC-SM05 | Error | ✓ | ✓ | Initial state not in vocabulary |

#### HC003 — Recognizer overlap

**Trigger:** Two types in the same vocabulary can both match the same token.

```
FUNCTION check_HC003(vocabulary):
    type_names ← vocabulary.base_types.keys()

    FOR EACH pair (A, B) IN combinations(type_names, 2):
        recog_A ← vocabulary.base_types[A]
        recog_B ← vocabulary.base_types[B]

        IF both are Sets:
            overlap ← recog_A ∩ recog_B
            IF overlap not empty:
                EMIT error(HC003,
                    f"Types '{A}' and '{B}' share values: {overlap}")

        IF one is Set, one is Predicate:
            // The static linter never executes application code, so it cannot evaluate the
            // predicate over the Set's members. It emits an info pointing to honest-test
            // (section 1.1); honest-test runs the predicate over each Set value at test time
            // and emits a warning for any value matched by both.
            EMIT info(HC003,
                "Set and predicate type may overlap on a Set value — verified by honest-test")

        IF both are Predicates:
            EMIT info(HC003,
                "Predicate × predicate overlap cannot be checked statically — verified by honest-test")
```

Both predicate-involved overlaps are statically undecidable (the predicate is opaque source), so the static rule emits an `info` directing the developer to the runtime check, exactly as section 1.1 prescribes. The `Error/Warning` severity in the rule table refers to the decidable Set × Set case (error) and the runtime Set × predicate case honest-test performs (warning); the static rule itself emits error (Set × Set) or info (any predicate involved).

#### HC006 — Composed type references unknown base type

```
FUNCTION check_HC006(vocabulary):
    FOR EACH comp IN vocabulary.composed_types:
        FOR EACH req_type IN comp.requires.keys():
            IF req_type NOT IN vocabulary.base_types:
                EMIT error(HC006, comp.name,
                    f"Composed type requires unknown base type '{req_type}'")

        capture_type ← unwrap_maybe(comp.captures)
        IF capture_type NOT IN vocabulary.base_types:
            EMIT error(HC006, comp.name,
                f"Composed type captures unknown base type '{capture_type}'")
```

#### HC007 — Empty chain

```
FUNCTION check_HC007(chain):
    IF len(chain.links) = 0:
        EMIT error(HC007, chain.name, "Chain has no links")
```

#### HC011 — Catch-all recognizer

A recognizer that accepts all (or nearly all) inputs is not a type. The vocabulary constructor must reject it.

```
FUNCTION check_HC011(recognizer, type_name):
    IF recognizer is a Set:
        // Sets are always bounded — not a catch-all
        RETURN

    // For predicates: sample 1000 random strings
    sample ← generate_random_strings(1000)
    accepted ← COUNT s IN sample WHERE recognizer(s) = true

    IF accepted / 1000 > 0.95:
        EMIT error(HC011, type_name,
            "Recognizer accepts nearly all inputs — not a discriminating type")
```

**Note:** HC011 requires running the predicate, which means it cannot be purely static. In CLI and LSP mode, honest-check uses a sandboxed evaluator. In startup mode, the `vocabulary()` constructor runs this check directly.

#### HC-SM01, HC-SM02, HC-SM05 — State machine vocabulary violations

```
FUNCTION check_state_machine_vocab(machine):
    FOR EACH (state, event) IN machine.transitions.keys():
        IF state NOT IN machine.states:
            EMIT error(HC-SM01, machine.name,
                f"State '{state}' in transition table not in states vocabulary")
        IF event NOT IN machine.events:
            EMIT error(HC-SM02, machine.name,
                f"Event '{event}' in transition table not in events vocabulary")

    IF machine.initial NOT IN machine.states:
        EMIT error(HC-SM05, machine.name,
            f"Initial state '{machine.initial}' not in states vocabulary")
```

### 4.2 Static Analysis Time

These rules require reading and analyzing source files. They fire in CLI and LSP mode. They do not fire at startup.

| Rule | Severity | LSP | Description |
|---|---|---|---|
| HC001 | Error | ✓ | Link missing vocabulary declaration |
| HC002 | Error | ✓ | Chain type mismatch between adjacent links |
| HC004 | Warning | ✓ | Dead vocabulary type |
| HC005 | Warning | ✓ | Unused binding entry |
| HC008 | Warning | ✓ | Impure link (framework tier) |
| HC009 | Warning | ✓ | Predicate may throw |
| HC010 | Warning | ✓ | Declared emission never produced |
| HC-SM03 | Warning | ✓ | Unreachable state |
| HC-SM04 | Warning | ✓ | Dead state (no outgoing transitions) |
| HC-P001 | Error | ✓ | if/elif/else dispatch chain |
| HC-P002 | Error | ✓ | Exception caught in non-boundary function |
| HC-P003 | Error | ✓ | Inheritance from non-framework base |
| HC-P004 | Error | ✓ | I/O inside non-boundary function |
| HC-P005 | Warning | ✓ | isinstance() / type() in business logic |
| HC-P006 | Warning | ✓ | Cache without profiling annotation |
| HC-P007 | Warning | ✓ | Instance state in constructor |
| HC-P010 | Error | ✓ | Non-serializable return value |
| HC-P011 | Error | ✓ | Framework lifecycle hook |
| HC-P013 | Error | ✓ | Unbounded database routing key |
| HC-P014 | Error | ✓ | Recognizer reused across slots |
| HC-P016 | Error | ✓ | Nonlocal closure over mutable state |
| HC-P017 | Error | ✓ | Serializer not declared as chain link |
| HC-R001 | Error | ✓ | Orphan function (no role, not reachable) |
| HC-OR001 | Error | ✓ | Orchestrator calls another orchestrator |
| HC-OR003 | Warning | ✓ | Suspected duplication between orchestrators |
| HC-A001 | Warning | ✓ | No AuthProvider registered; actor-using operations unverifiable |
| HC-A002 | Error | ✓ | Actor trusted from request input instead of the boundary |
| HC-HF001 | Error | ✓ | feature_state references a flag not declared in FEATURES |
| HC-HF002 | Warning | ✓ | Handler table missing an entry for a declared flag state |

#### HC001 — Link missing vocabulary

```
FUNCTION check_HC001(chain):
    FOR EACH link IN chain.links:
        IF link has no honest_type metadata:
            EMIT error(HC001, link.name,
                "Function in chain has no vocabulary declared. "
                "Wrap with @link(accepts=..., emits=...) or link() constructor.")
```

#### HC002 — Chain type mismatch

```
FUNCTION check_HC002(chain):
    FOR i FROM 1 TO len(chain.links) - 1:
        emits   ← chain.links[i-1].emits.type_names
        accepts ← chain.links[i].accepts.type_names
        missing ← accepts - emits

        IF missing is not empty:
            EMIT error(HC002, chain.links[i].name,
                f"Accepts types not provided by previous link: {missing}")
```

The first link has no predecessor, but its input is not unknown: it receives the manifest `classify()` produces at intake from the request the templates send — the closed, statically-inspectable input boundary (see honest-framework-spec.md, "The input boundary is closed"). So the first link's `accepts` is checked against that **derived** boundary vocabulary, not a separately declared one. The derivation follows the route map (honest-page-architecture.md §9): for a chain, take its `(method, path)` entries; find the templates whose `hx-post`/`hx-get` target those paths; the union of the fields those templates send — the application-state manifest keys (honest-page §5), the form field `name`s, and the `hx-vals` keys, plus the route's path and query parameters — is the boundary vocabulary. A field name that is not statically resolvable (a fully dynamic template expression) makes the boundary unknowable and is itself a violation. A first link declared `boundary=True` is the intake boundary itself and is exempt (it receives the raw request, by design); a first link that declares no vocabulary at all is HC001's concern, exactly as for any other link.

#### HC004 — Dead vocabulary type

```
FUNCTION check_HC004(vocabulary, binding):
    IF binding is auto_binding: RETURN

    FOR EACH type_name IN vocabulary.base_types:
        in_binding  ← type_name IN binding
        in_composed ← ANY comp IN vocabulary.composed_types
                       WHERE type_name IN comp.requires
                       OR type_name = comp.captures

        IF NOT in_binding AND NOT in_composed:
            EMIT warning(HC004, type_name,
                "Type defined in vocabulary but never bound or composed")
```

#### HC005 — Unused binding

```
FUNCTION check_HC005(vocabulary, binding):
    IF binding is auto_binding: RETURN

    FOR EACH (type_name, slot) IN binding:
        IF type_name NOT IN vocabulary.base_types
        AND type_name NOT IN vocabulary.composed_type_names:
            EMIT warning(HC005, type_name,
                f"Binding references type '{type_name}' not found in vocabulary")
```

#### HC008 — Impure link

The impurity watch list is exhaustive and **conformance-tested**. Every item below must be trapped by a conformant honest-check implementation; if any item is missed, the implementation fails the conformance suite. The list is not "representative examples" — it is the normative set.

```
FUNCTION check_HC008(link):
    IF link.boundary = True: RETURN

    ast ← link.function_ast
    violations ← []

    io_calls ← IO_WATCH_LIST[language]

    FOR EACH call IN ast.all_calls:
        IF call.name IN io_calls:
            APPEND call.name TO violations

    FOR EACH name_ref IN ast.name_references:
        IF name_ref is a global variable (not a function or frozen constant):
            APPEND name_ref TO violations

    FOR EACH call IN ast.all_calls:
        IF call.name IN NONDETERMINISTIC_WATCH_LIST[language]:
            APPEND call.name TO violations

    IF violations not empty:
        EMIT warning(HC008, link.name,
            f"Link may be impure: {violations}. "
            "Add boundary=True if I/O is intentional.")
```

**IO_WATCH_LIST (Python):**

```
# Filesystem
"open", "pathlib.Path.open", "pathlib.Path.read_text", "pathlib.Path.write_text",
"pathlib.Path.read_bytes", "pathlib.Path.write_bytes", "os.open", "os.read",
"os.write", "os.remove", "os.rename", "os.mkdir", "os.rmdir", "os.listdir",
"os.walk", "shutil.copy", "shutil.move", "shutil.rmtree", "tempfile.*",
"mmap.mmap",

# Process / shell
"subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_output",
"os.system", "os.popen", "os.execvp", "os.spawn*", "os.fork",

# Network
"socket.*", "http.client.*", "urllib.request.*", "urllib.urlopen",
"requests.*", "httpx.*", "aiohttp.*", "urllib3.*", "smtplib.*",
"ftplib.*", "poplib.*", "imaplib.*", "telnetlib.*", "ssl.*",

# Process state / stdio
"print", "input", "sys.stdout.write", "sys.stderr.write",
"sys.stdin.read", "logging.*",

# Database drivers
"psycopg2.connect", "psycopg.connect", "asyncpg.connect", "sqlite3.connect",
"aiosqlite.connect", "pymongo.MongoClient", "redis.Redis",
```

**NONDETERMINISTIC_WATCH_LIST (Python):**

```
# Randomness
"random.*", "secrets.*", "uuid.uuid1", "uuid.uuid3", "uuid.uuid4", "uuid.uuid5",
"os.urandom", "hashlib.*.hexdigest" (when fed non-deterministic input),

# Time
"time.time", "time.time_ns", "time.monotonic", "time.perf_counter",
"time.process_time", "time.sleep",
"datetime.datetime.now", "datetime.datetime.utcnow", "datetime.datetime.today",
"datetime.date.today",

# Environment / process
"os.environ", "os.getenv", "os.getlogin", "os.getpid", "os.getppid",
"os.getcwd", "os.uname", "os.environ.get", "getpass.getpass", "getpass.getuser",
"platform.*", "sys.argv", "sys.version", "sys.path" (read),
"__file__", "__name__" (read in non-module-init context),

# Thread / process state
"threading.current_thread", "threading.get_ident", "threading.active_count",
"multiprocessing.current_process", "multiprocessing.cpu_count",
"asyncio.get_event_loop", "asyncio.current_task",

# Object identity (non-deterministic across runs)
"id",

# Hash of mutable / unordered containers (set, dict) — hash order non-deterministic
"hash" (when argument is a set or frozenset of heterogeneous types),
```

**IO_WATCH_LIST (JavaScript / TypeScript):**

```
# Filesystem / Node
"fs.*", "fsp.*", "fs/promises.*", "path.*" (when used for I/O),

# Network
"fetch", "XMLHttpRequest", "http.request", "https.request",
"WebSocket", "EventSource", "navigator.sendBeacon",

# Storage (browser)
"localStorage.*", "sessionStorage.*", "indexedDB.*", "caches.*",

# Process / stdio
"process.stdout.write", "process.stderr.write", "process.stdin.*",
"console.log", "console.error", "console.warn", "console.info", "console.debug",

# Database drivers
"pg.*", "mongodb.*", "redis.*", "mysql.*", "sqlite3.*",
```

**NONDETERMINISTIC_WATCH_LIST (JavaScript / TypeScript):**

```
# Randomness
"Math.random", "crypto.getRandomValues", "crypto.randomUUID",

# Time
"Date.now", "new Date()", "performance.now",

# Environment / process
"process.env", "process.pid", "process.cwd", "process.argv",
"process.platform", "process.version",
"navigator.*", "location.*", "document.cookie" (read),

# Object identity
"Symbol()", "Symbol.for" (when the key is computed non-deterministically),
```

**Other languages (Ruby, Go):** conformance watch lists are published in the hub repository at `honest/honest-check-conformance/watch-lists/{language}.json`. Implementations must cover every entry in the published list for their declared language.

**What is NOT in the watch list:** pure computation, data-structure construction and access on immutable types, module-level constants bound to immutable values, function definitions. These do not trigger HC008.

**What global reads ARE flagged:** any read of a module-level `list`, `dict`, `set`, or other mutable container; any read of a module-level variable that is not `Final` / `const` / frozen. Reads of module-level function definitions and frozen constants (tuples, frozensets, `dataclasses.frozen=True`) are not flagged.

#### HC009 — Predicate may throw

```
FUNCTION check_HC009(vocabulary):
    FOR EACH (type_name, recognizer) IN vocabulary.base_types:
        IF recognizer is a predicate:
            ast ← recognizer.function_ast
            risky ← []

            FOR EACH node IN ast:
                IF node is int(), float(), index_access, division:
                    APPEND node TO risky

            IF risky not empty:
                EMIT warning(HC009, type_name,
                    f"Predicate may throw on non-matching input: {risky}. "
                    "Wrap in try/except or guard with isinstance().")
```

#### HC010 — Declared emission never produced

```
FUNCTION check_HC010(link):
    emitted_types ← link.emits.type_names
    ast           ← link.function_ast
    produced_keys ← extract_manifest_assignments(ast)
    produced_types ← { binding_reverse[key] FOR key IN produced_keys }
    phantom ← emitted_types - produced_types - link.accepts.type_names

    IF phantom not empty:
        EMIT warning(HC010, link.name,
            f"Link declares emission of types never produced: {phantom}")
```

#### HC-SM03, HC-SM04 — Unreachable and dead states

```
FUNCTION check_state_machine_reachability(machine):
    reachable ← { machine.initial }
    frontier  ← { machine.initial }

    WHILE frontier is not empty:
        next ← {}
        FOR EACH state IN frontier:
            FOR EACH (s, e), target IN machine.transitions:
                IF s = state AND target NOT IN reachable:
                    reachable.ADD(target)
                    next.ADD(target)
        frontier ← next

    FOR EACH state IN machine.states:
        IF state NOT IN reachable AND state ≠ machine.initial:
            EMIT warning(HC-SM03, machine.name,
                f"State '{state}' is unreachable")

    FOR EACH state IN machine.states:
        has_outgoing ← ANY (s, e) IN machine.transitions WHERE s = state
        is_terminal  ← state IN (machine.terminal OR [])
        IF NOT has_outgoing AND NOT is_terminal:
            EMIT warning(HC-SM04, machine.name,
                f"State '{state}' has no outgoing transitions and is not declared terminal")
```

#### HC-P001 — if/elif/else dispatch chain

```
FUNCTION check_HC_P001(ast):
    FOR EACH if_node IN ast.all_if_statements:
        branches ← count_elif_else_branches(if_node)
        IF branches >= 3:
            IF condition_dispatches_on_value(if_node):
                EMIT error(HC-P001, if_node.location,
                    "if/elif/else chain dispatches on value — use dict lookup. "
                    "See honest-code-principles.md §3.")
```

Detection: three or more string/enum equality tests on the same variable, e.g. `if x == "a": ... elif x == "b": ... elif x == "c":`.

#### HC-P002 — Exception caught in non-boundary function

Honest Code principle *Typed Exceptions at the Boundary*: business logic does not catch. Functions raise; the boundary (route handler, supervisor, or any `@boundary` / `@link(boundary=True)` function) catches, inspects the typed exception, and maps it to a response. A `try`/`except` inside a non-boundary function is a structural violation — it swallows faults, hides control flow inside the raise/catch pair, and produces a result auto-generation cannot verify, because the caught path is invisible to the manifest. Faults inside business logic must be **data** (rejections, faults), not exceptions.

> **Note.** This rule was formerly "class with mutating methods." That rule was redundant: Honest Code admits no classes (HC-P003 permits only TypedDict / Protocol / ABC / Exception bases, none of which carry mutating behaviour), so there is no "class with mutating methods" to police. The poka-yoke inventory always assigned HC-P002 to *typed faults at the boundary*; the rule now matches the inventory.

```
FUNCTION check_HC_P002(ast):
    FOR EACH function_def IN ast.all_functions:
        IF function_def is a boundary (decorated @boundary or @link(boundary=True)):
            CONTINUE
        FOR EACH try_stmt IN function_def.body:
            IF try_stmt has an except clause:
                EMIT error(HC-P002, try_stmt.location,
                    f"Function '{function_def.name}' catches an exception in business "
                    "logic. Let the function raise; catch at the boundary (@boundary / "
                    "route handler), or return a fault as data. A `try`/`finally` with "
                    "no `except` is permitted for cleanup, but prefer a context manager.")
```

A `try` with only a `finally` (cleanup, no `except`) is not a catch and does not fire HC-P002, though Honest Code prefers a context manager (principle *Context Managers Over Instance State*). The rule eliminates the bug category the poka-yoke inventory names under *Typed faults at the boundary*: exception swallowing, control-flow-via-raise, and unchecked exception propagation inside business logic.

#### HC-P003 — Class declaration

A class definition is permitted only when it subclasses one of the framework-approved bases (`TypedDict`, `Protocol`, `ABC`, `Exception`, `BaseException`, `Error`). Both inheriting from a non-approved base AND declaring a class with no explicit base (which implicitly inherits from `object` in Python) are violations — `object` is not an approved base.

```
FUNCTION check_HC_P003(ast):
    allowed_bases ← {"TypedDict", "Protocol", "ABC", "Exception",
                      "BaseException", "Error"}  // language-specific

    FOR EACH class_def IN ast.all_classes:
        IF class_def.bases IS EMPTY:
            // Bare class: implicit object base in Python; not approved.
            EMIT error(HC-P003, class_def.location,
                f"Class '{class_def.name}' has no declared base. "
                "Honest Code permits class definitions only as subclasses of "
                "TypedDict, Protocol, ABC, or a declared Exception. "
                "Use a TypedDict for data shapes or a pure function.")
            CONTINUE

        FOR EACH base IN class_def.bases:
            IF base NOT IN allowed_bases:
                EMIT error(HC-P003, class_def.location,
                    f"Class '{class_def.name}' inherits from '{base}'. "
                    "Use composition over inheritance.")
```

**Why this matters.** A bare `class Foo:` is the main way non-honest code sneaks in. It can hold hidden state (class attributes and changeable instance state) and stand in for if/elif/else by dispatching through method lookup. Without the empty-bases check, someone could add a class that slips past HC-P003, hide state in it, and defeat the purity and repeat-run guarantees. With the check, every class that is not a data-shape declaration (TypedDict) or a typed error (Exception subclass) fails test generation and the code is turned away as dishonest.

#### HC-P004 — I/O inside non-boundary function

Same detection as HC008, elevated from warning to error for the principle tier. A function not declared as a boundary that performs I/O is a structural violation of Honest Code principle 4.

#### HC-P005 — isinstance() / type() in business logic

```
FUNCTION check_HC_P005(ast):
    FOR EACH call IN ast.all_calls:
        IF call.name IN {"isinstance", "type"}:
            IF NOT in_boundary_function(call):
                EMIT warning(HC-P005, call.location,
                    "isinstance() check in business logic. "
                    "Consider vocabulary declaration instead.")
```

#### HC-P006 — Cache without profiling annotation

```
FUNCTION check_HC_P006(ast):
    cache_patterns ← {
        decorators: {"lru_cache", "cache", "memoize", "cached_property"},
        imports:    {"redis", "memcache"},
        patterns:   ["if key in _cache"],
    }

    FOR EACH cache_use IN find_cache_patterns(ast, cache_patterns):
        IF NOT has_profiling_annotation(cache_use):
            EMIT warning(HC-P006, cache_use.location,
                "Cache detected without profiling evidence. "
                "Add @profiled annotation or # honest: profiled comment.")
```

#### HC-P007 — Instance state in constructor

```
FUNCTION check_HC_P007(ast):
    FOR EACH class_def IN ast.all_classes:
        init ← class_def.get_method("__init__")
        IF init:
            FOR EACH assignment IN init.assignments_to_self:
                IF assignment.name starts with "_":
                    EMIT warning(HC-P007, assignment.location,
                        f"Instance state '{assignment.name}'. "
                        "Pass as parameter or use context manager.")
```

#### HC-P010 — Non-serializable return value

```
FUNCTION check_HC_P010(ast):
    FOR EACH function_def IN ast.pure_functions:
        FOR EACH return_stmt IN function_def.return_statements:
            IF return_stmt.value is class_instance:
                IF NOT is_typeddict(return_stmt.value):
                    EMIT error(HC-P010, return_stmt.location,
                        "Pure function returns non-serializable object. "
                        "Use TypedDict or dict.")
```

#### HC-P011 — Framework lifecycle hook

```
FUNCTION check_HC_P011(ast):
    lifecycle_hooks ← {
        "useEffect", "useLayoutEffect", "componentDidMount",
        "componentDidUpdate", "componentWillUnmount",
        "ngOnInit", "ngOnDestroy",
        "addEventListener", "removeEventListener",
    }

    FOR EACH call IN ast.all_calls:
        IF call.name IN lifecycle_hooks:
            EMIT error(HC-P011, call.location,
                f"Lifecycle hook '{call.name}'. "
                "Use HTMX attributes or server-rendered HTML.")
```

#### HC-P013 — Unbounded database routing key

A manifest key that routes to a database — `db_id`, `tenant_id`, or `credential` — bound to a predicate recognizer rather than a bounded Set lets an arbitrary identifier reach the pool layer. The vocabulary is the whitelist; a predicate bypasses it. The rule is specified by honest-persist section 8.4 and reproduced here as the canonical HC reference.

```
FUNCTION check_HC_P013(vocabulary, binding):
    routing_keys = {"db_id", "tenant_id", "credential"}

    FOR EACH (type_name, slot) IN binding:
        IF slot IN routing_keys:
            recognizer = vocabulary.base_types.get(type_name)
            IF recognizer is a predicate:
                EMIT error(HC-P013, type_name,
                    f"Routing key '{slot}' is bound to predicate recognizer "
                    f"'{type_name}' — use a bounded Set recognizer instead")
```

**Why this matters.** A connection pool routes on whatever the manifest carries. If the routing key is validated by a predicate (any string the predicate accepts), a caller can name a database the application never declared, and the pool will try to reach it. A bounded Set makes the set of reachable databases a closed, declared list — the type system becomes the access-control list. A ref recognizer is not flagged at the binding site: it names a recognizer defined elsewhere, and resolving it is out of scope for this structural check.

#### HC-P014 — Recognizer reused across slots

A single recognizer bound to two or more slot names in the same binding is a field-swap vulnerability. Auto-generation can enumerate valid values against the recognizer, but cannot detect that the wrong value has been placed in the wrong slot — the chain-contract check sees a type-valid manifest.

```
FUNCTION check_HC_P014(bindings):
    FOR EACH binding IN bindings:
        recognizer_to_slots ← {}

        FOR EACH (recognizer_name, slot_name) IN binding.entries:
            APPEND slot_name TO recognizer_to_slots[recognizer_name]

        FOR EACH (recognizer_name, slot_list) IN recognizer_to_slots:
            IF len(slot_list) > 1:
                EMIT error(HC-P014,
                    f"Recognizer '{recognizer_name}' is bound to multiple slots: "
                    f"{slot_list}. Each slot must have a semantically distinct "
                    f"recognizer (e.g., sender_id / receiver_id rather than two "
                    f"bindings of user_id). Without semantic separation, the chain "
                    f"contract cannot catch a swap between these slots.")
```

**Why this matters.** Swapping two arguments of the same kind (e.g. `transfer(from_id, to_id)` → `transfer(to_id, from_id)`) produces a manifest that passes every recognizer check, passes chain contracts, and passes purity — but behaves wrong. An end-to-end test catches the swap by checking observable behaviour; the generated suite cannot, because the type system has folded both slots into one kind. HC-P014 forces the developer either to use a distinct recognizer per slot or to accept that test generation must be backed up by a BDD scenario at the requirement level. When HC-P014 fires, test generation fails and the code is turned away as dishonest.

**Resolution patterns:**

1. **Distinct recognizers per semantic role.** `sender_id`, `receiver_id`, `assignee_id` — each with its own value space (e.g., prefixed IDs: `snd_<uuid>`, `rcv_<uuid>`).
2. **Composed / sum types.** Declare a `transfer` composed type that captures `{from: user_id, to: user_id}` as a single slot. The composed type preserves both values but binds as a single slot.
3. **Explicit acknowledgement.** A `# honest: allow-recognizer-reuse <reason>` comment suppresses HC-P014 at the binding site, but requires a BDD feature file named `{chain_name}_swap.feature` to be present and cover each slot's semantic role. honest-test verifies the feature presence.

#### HC-P016 — Nonlocal closure over mutable state

A function that captures a name from an enclosing scope via `nonlocal` (or equivalent) and mutates it hides state outside class declarations — closures are the non-class vector for smuggling state into otherwise-pure-looking functions.

```
FUNCTION check_HC_P016(ast):
    FOR EACH function_def IN ast.all_functions:
        FOR EACH inner_function IN function_def.nested_functions:
            FOR EACH stmt IN inner_function.body:
                IF stmt is "nonlocal X":
                    // Does inner_function mutate X?
                    IF ANY mutation of X in inner_function.body:
                        EMIT error(HC-P016, inner_function.location,
                            f"Inner function '{inner_function.name}' captures "
                            f"'{X}' via nonlocal and mutates it. Closures may "
                            f"not carry mutable state — use pure parameters "
                            f"or move state into persist.")
```

**Language equivalents:**

| Language | Mutable-closure pattern to detect |
|---|---|
| Python | `nonlocal x; x = ...` or `nonlocal x; x += ...` |
| JavaScript | `let x = ...; return () => { x = ... }` (outer `let`/`var` captured and mutated) |
| Ruby | block captures local and mutates it via `|=`, `+=`, etc. |
| Go | Goroutine captures outer variable and mutates it |

#### HC-P017 — Serializer not declared as chain link

Any function that produces HTTP output (response body, headers, status, cookies) must either be a `@link` with declared `emits` vocabulary covering the full protocol surface, or must compose exclusively with a declared serializer `@link`. Inline serialization inside a non-link function escapes chain contract testing — the serializer's output is not classified by any vocabulary, so mutations in the serializer cannot be detected by auto-generation.

```
FUNCTION check_HC_P017(ast):
    http_response_markers ← {"Response", "JSONResponse", "HTMLResponse",
                              "res.send", "res.json", "res.status",
                              "render", "ctx.body = ...", ...}  // language-specific

    FOR EACH function_def IN ast.all_functions:
        IF function_def produces http_response_markers:
            IF function_def IS NOT @link OR function_def.emits is unset:
                EMIT error(HC-P017, function_def.location,
                    f"Function '{function_def.name}' produces HTTP output "
                    f"without being a declared @link with emits vocabulary. "
                    f"Declare emits covering status, content-type, headers, "
                    f"body shape, and cookies; or delegate to a declared "
                    f"serializer link.")
```

The `emits` vocabulary for an HTTP-producing link must include at minimum: a status recognizer, a Content-Type recognizer, and a body-shape recognizer. Additional recognizers for individual headers and cookies are required whenever the function sets them.

#### HC-R001 — Orphan function (no role, not reachable from any role)

Every function in source must have exactly one of the declared roles — `@link`, `@recognizer`, `@boundary`, `@helper` — or must be reachable by static call analysis from a function that does. Auto-generation exercises all roled functions through vocabulary enumeration; helpers are exercised transitively via call graphs. A function with no role and no reachable-from-roled caller is an orphan — auto-generation does not reach it, so it has no test coverage, so the code is dishonest.

```
FUNCTION check_HC_R001(source_tree):
    roled ← { fn FOR fn IN all_functions IF fn.role IN {link, recognizer, boundary, helper} }
    call_graph ← build_static_call_graph(source_tree)
    reachable ← transitive_closure(roled, call_graph)

    orphans ← all_functions - reachable

    FOR EACH orphan IN orphans:
        EMIT error(HC-R001, orphan.location,
            f"Function '{orphan.name}' has no declared role and is not called "
            f"by any roled function. Auto-generation cannot reach it, so no "
            f"tests will be generated for it. Declare a role with @link, "
            f"@recognizer, @boundary, or @helper — or remove the function.")
```

**Role semantics:**

| Role | How auto-generation exercises it |
|---|---|
| `@link` | Exhaustive vocabulary enumeration of `accepts` through the link |
| `@recognizer` | Every Set member + adversarial neighbors; Fibonacci for numeric predicates |
| `@boundary` | Called during chain integration; I/O side-effects declared, not tested for purity |
| `@helper` | Transitively exercised by the callers that reach it; must be branchless (HC-P001) so every reachable call path is exhaustive |

This rule unifies the coverage story: no function escapes auto-generation, because no function is permitted to exist outside the role-declaration-plus-reachability graph.

#### HC-OR001 — Orchestrator calls another orchestrator

Orchestrators are the root of a request or operation. They wire input I/O, chain execution, and output I/O. They are **not composable with other orchestrators**. If a function declared `role=orchestrator` (or `@orchestrator`) contains a direct call to another declared orchestrator, it is a structural violation. The intended refactor: extract the shared logic as a pure helper (if side-effect-free) or as a chain (if I/O is involved), and have both orchestrators invoke that.

```
FUNCTION check_HC_OR001(ast):
    declared_orchestrators ← { fn FOR fn IN ast.all_functions IF fn.role = "orchestrator" }
    orch_names ← { fn.name FOR fn IN declared_orchestrators }

    FOR each orchestrator IN declared_orchestrators:
        FOR each call IN orchestrator.body.all_calls:
            IF call.name IN orch_names:
                EMIT error(HC-OR001, call.location,
                    f"Orchestrator '{orchestrator.name}' calls orchestrator "
                    f"'{call.name}'. Orchestrators are the root of an operation and "
                    f"do not compose. Extract the shared logic as a pure helper "
                    f"(if no I/O) or as a chain (if I/O is involved).")
```

**Rationale:** Orchestrator composition is the "dispatcher of dispatchers" anti-pattern Honest Code explicitly rejects. It re-introduces the invisible nesting the 4-column architecture model is built to prevent. The single-root constraint keeps I/O accounting visible and the wire-up layer auditable at a glance.

#### HC-OR003 — Suspected duplication between orchestrators

Soft rule. Static AST-based duplication detection across orchestrator bodies. When two or more orchestrators share a run of N or more consecutive equivalent call expressions (N configurable, default 3), emit a warning suggesting extraction.

```
FUNCTION check_HC_OR003(ast, min_run: int = 3):
    orchestrators ← [fn FOR fn IN ast.all_functions IF fn.role = "orchestrator"]
    normalized ← { orch.name: normalize_ast(orch.body) FOR orch IN orchestrators }

    FOR each pair (a, b) IN combinations(orchestrators, 2):
        lcs ← longest_common_subsequence(normalized[a.name], normalized[b.name])
        IF len(lcs) >= min_run:
            EMIT warning(HC-OR003,
                f"Orchestrators '{a.name}' and '{b.name}' share {len(lcs)} "
                f"consecutive operations. Consider extracting the shared sequence "
                f"as a pure helper (if side-effect-free) or as a chain (if I/O is "
                f"involved). Orchestrators are not composable (HC-OR001); "
                f"reusable orchestration logic belongs in helpers or chains.")
```

**Soft rule, not error.** A developer may have legitimate reasons to keep two similar orchestrators distinct (e.g., different fault-mapping strategies). HC-OR003 surfaces the pattern without forcing the refactor. Developers suppress per-case with `# honest: ignore HC-OR003` when the duplication is intentional.

**Why soft:** duplication detection is inherently heuristic. Cosmetic-vs-structural duplication is a judgment call that belongs in the edit, not the linter. But surfacing the detection keeps the orchestrator-extraction principle visible during development.

**Companion to HC-OR001.** HC-OR001 catches the direct case (orchestrator calls orchestrator). HC-OR003 catches the latent case (orchestrators are evolving toward an unstated shared pattern; extract it before the temptation to compose them arises).

**Interaction with HC008 (impurity in non-boundary function):** if a developer responds to HC-OR003 by extracting a shared helper that happens to contain I/O, HC008 flags it. The two rules together force the correct choice: shared logic with I/O becomes a chain (containing `boundary=True` links), not an impure helper.

#### HC-A001 — No AuthProvider registered

```
FUNCTION check_HC_A001(application_context):
    provider ← get_registered_auth_provider()

    IF provider IS NONE:
        actor_using_ops ← [O FOR O IN all_operations IF O acts on behalf of an actor]
        IF actor_using_ops IS NOT EMPTY:
            EMIT warning(HC-A001,
                "No AuthProvider registered. "
                f"These operations act on behalf of an actor but no boundary "
                f"validator resolves one: {actor_using_ops}. "
                f"Register a provider (e.g., example-auth-pro), or remove the "
                f"actor dependency.")
```

**Severity:** Warning. An application with no authentication may be intentional (read-only public applications, local development). The warning surfaces the gap without blocking honest-check from passing. HC-A002 (below) is the blocking rule for an operation that takes its actor from request input.

#### HC-A002 — Actor trusted from request input

A link declared `authorizes=True` must use the actor resolved at the boundary (honest-auth `resolve_actor`), which the framework passes inward as `actor`. A link that does not reference `actor` is sourcing identity from request input (body, query string, form fields, the manifest) — forgeable. Identity is established once, at the boundary, and flows inward as data.

```
FUNCTION check_HC_A002(link, provider_registered):
    IF NOT provider_registered: RETURN          // HC-A001 handles the no-provider case
    IF link.authorizes = False: RETURN

    IF "actor" NOT referenced_in link.body:
        EMIT error(HC-A002, link.location,
            f"Link '{link.name}' declares authorizes=True but does not use the "
            f"boundary-resolved actor ('actor'). Actor identity must come from the "
            f"boundary, not be trusted from request input.")
```

#### HC-HF001 / HC-HF002 — Feature-flag references

The two feature-flag rules are specified in full in honest-features §7; honest-check implements them. Both read the module-scope `FEATURES` vocabulary and the `feature_state(state, "flag")` call sites, and are checked only when `FEATURES` is a readable module-scope dict literal.

- **HC-HF001 (error)** — a `feature_state(state, "flag")` call whose flag (the second positional, a string literal) is not a key in `FEATURES`. An undeclared flag raises `KeyError` at runtime.
- **HC-HF002 (warning)** — a handler table dispatched as `TABLE[feature_state(state, "flag")]` whose dict literal is missing an entry for one of `FEATURES["flag"]["states"]`. A missing entry raises `KeyError` when the flag enters that state.

```
FUNCTION check_HC_HF001(features, calls):
    IF features is empty: RETURN          // no readable FEATURES to verify against
    FOR EACH (flag, call) IN calls:
        IF flag NOT IN features:
            EMIT error(HC-HF001, call.location,
                f"feature_state references '{flag}', which is not a declared flag in FEATURES.")
```

### 4.3 Test Time (Deferred to honest-test)

These rules cannot be verified statically. honest-check emits an `info` diagnostic noting they are verified by honest-test. They are listed here for completeness.

| Rule | Owner | Description |
|---|---|---|
| HC003 (predicate × predicate) | honest-test | Predicate overlap requires empirical testing |
| HC011 (predicate sampling) | honest-test | Catch-all predicate detection via sampling |
| HC-P008 | honest-test | Gherkin step too long |
| HC-P009 | honest-test | Chain missing .feature file |
| HC-P012 | honest-test | Excessive mocks in test |

### 4.4 Link Declaration

A link declares its vocabulary for static verification. The declaration does not restrict runtime access.

```python
@link(
    accepts  = format_vocab,
    emits    = format_vocab | result_vocab,
    boundary = False,
)
def format_value(manifest):
    ...
```

The `@link` decorator / `link()` wrapper:
1. Attaches vocabulary metadata for honest-check introspection
2. Does not modify the function's runtime behavior
3. Does not scope or filter the manifest passed to the function

`emits` uses `|` (vocabulary merge) to express "everything I received, plus what I added."

---

## 5. Language Guidance

The rules in section 4 are language-agnostic. This section maps each rule to its natural form in each target language. Implementors must support the canonical detection described in section 4; this section provides translation guidance to ensure no rule is accidentally missed due to syntactic differences.

### 5.1 HC-P001: Dispatch Chain

| Language | Pattern to detect |
|---|---|
| Python | `if x == "a": ... elif x == "b": ... elif x == "c":` |
| JavaScript/TypeScript | `if (x === 'a') ... else if (x === 'b') ... else if (x === 'c')` |
| Ruby | `if x == 'a' ... elsif x == 'b' ... elsif x == 'c'` |
| Go | `if x == "a" ... else if x == "b" ... else if x == "c"` or `switch x { case "a": ... case "b": ... case "c": }` |

Note: Go `switch` statements are semantically dict lookups and are HC-P001 compliant. `if/else if` chains in Go are violations.

### 5.2 HC-P002: Exception Caught in Non-Boundary Function

| Language | Catch construct to detect in non-boundary functions |
|---|---|
| Python | `try: ... except ...:` |
| JavaScript / TypeScript | `try { ... } catch (e) { ... }` |
| Ruby | `begin ... rescue ... end`, or inline `rescue` |
| Go | `recover()` inside a deferred function |

A `try`/`finally` (or equivalent) with no catch clause is cleanup, not catching, and is compliant — though a context manager is preferred (HC-P007 / principle *Context Managers Over Instance State*). Boundary functions (`@boundary`, `@link(boundary=True)`, route handlers) may catch.

**Marking a boundary in a language without decorators.** Python and TypeScript mark a boundary with `@boundary` / `@link(boundary=True)`. Vanilla JavaScript has no decorator syntax, so honest-check marks a boundary with a `// honest: boundary` comment on the function's line or the line immediately above it. Inside a function so marked, I/O (HC-P004) and a caught exception (HC-P002) are intentional and are not flagged. This is the same directive comment channel as `// honest: ignore`, so it needs no new syntax.

### 5.3 HC-P003: Class declaration

| Language | Allowed bases | Violations |
|---|---|---|
| Python | `TypedDict`, `Protocol`, `ABC`, `Exception` | `class X(Y)` with Y not in allowed; `class X:` with no declared base |
| JavaScript/TypeScript | No `extends` except `Error` | `class X extends Y`; `class X {}` |
| Ruby | `StandardError`, `RuntimeError` | Any `class X`; any `class X < Y` with Y not in allowed |
| Go | Go has no class inheritance — HC-P003 does not apply | N/A |

**Bare class declarations** (no explicit base) are violations in every language that treats such a class as implicitly extending a root type (Python's `object`, Ruby's `Object`, JavaScript's `Object`). These root types are not framework-approved bases, and the implicit inheritance is still inheritance.

Go's interface system is structurally compliant with Honest Code principles. Embedding (`type X struct { Y }`) is flagged as HC-P007 (instance state) if the embedded type carries mutable state.

### 5.4 HC-P004/HC008: I/O Detection

| Language | I/O patterns to detect |
|---|---|
| Python | `open()`, `requests.*`, `urllib.*`, `subprocess.*`, `os.system()`, `print()` (in non-boundary functions) |
| JavaScript | `fetch()`, `fs.*`, `http.*`, `console.log()` (in non-boundary functions) |
| Ruby | `File.*`, `Net::HTTP`, `open()`, `puts` (in non-boundary functions) |
| Go | `os.*`, `net.*`, `fmt.Print*` (in non-boundary functions) |

### 5.5 HC-P005: Type Checking

| Language | Pattern to detect |
|---|---|
| Python | `isinstance(x, T)`, `type(x) == T`, `type(x) is T` |
| JavaScript/TypeScript | `typeof x === 'string'`, `x instanceof T` |
| Ruby | `x.is_a?(T)`, `x.kind_of?(T)`, `x.class == T` |
| Go | Type assertions `x.(T)` and type switches `switch x.(type)` outside boundary functions |

### 5.6 HC-P006: Cache Detection

| Language | Cache patterns |
|---|---|
| Python | `@lru_cache`, `@cache`, `@cached_property`, direct dict cache patterns |
| JavaScript | `Map` used as cache, `WeakMap` cache patterns, `memoize` imports |
| Ruby | `||=` memoization pattern (`@result ||= compute()`), `Rails.cache.*` |
| Go | `sync.Map`, package-level map variables used as cache |

The JavaScript implementation flags the constructs that are caches by nature — `new WeakMap()` (a WeakMap's only use is associating data with objects, i.e. memoization) and `memoize` / `memoizeOne` calls. A bare `new Map()` is **not** flagged: a Map is a general-purpose collection, and "used as cache" is not statically decidable without flow analysis, so flagging every Map would be a false positive. As with any warning, `// honest: ignore HC-P006` dismisses it once the path is profiled.

### 5.7 HC-P011: Lifecycle Hooks

| Language | Hooks to detect |
|---|---|
| JavaScript | `useEffect`, `useLayoutEffect`, `componentDidMount`, `addEventListener` |
| TypeScript | Same as JavaScript plus Angular `ngOnInit`, `ngOnDestroy` |
| Ruby | Rails `before_action`, `after_action`, `before_save` (in non-model contexts) |
| Python | FastAPI `@app.on_event("startup")` outside of legitimate startup registration |
| Go | No direct equivalent — flag `http.HandleFunc` calls inside business logic functions |

---

## 6. Output Format

### 6.1 Human-readable (CLI default)

```
honest-check src/

src/pipelines/user.py:42:5: error HC-P001
  if/elif/else chain dispatches on value — use dict lookup.
  See honest-code-principles.md §3.
  |
  42 | if role == "admin":
  43 |     return admin_view(manifest)
  44 | elif role == "editor":
  45 |     return editor_view(manifest)
  ...

src/vocab/format.py:18:1: warning HC004
  Type 'style_name' defined in vocabulary but never bound or composed.

src/chains/report.py:67:1: error HC002
  Link 'render_pdf' accepts types not provided by previous link 'format_numbers': {'locale'}

Found 2 errors, 1 warning.
```

### 6.2 JSON (CI and tooling)

```json
{
    "version": "0.1",
    "timestamp": "2026-03-15T...",
    "summary": {
        "errors": 2,
        "warnings": 1,
        "infos": 0
    },
    "diagnostics": [
        {
            "rule":     "HC-P001",
            "severity": "error",
            "file":     "src/pipelines/user.py",
            "line":     42,
            "col":      5,
            "message":  "if/elif/else chain dispatches on value — use dict lookup.",
            "context":  "if role == \"admin\":",
            "fixable":  false
        }
    ]
}
```

### 6.3 GitHub Annotations

```
::error file=src/pipelines/user.py,line=42,col=5,title=HC-P001::if/elif/else chain dispatches on value — use dict lookup.
::warning file=src/vocab/format.py,line=18,col=1,title=HC004::Type 'style_name' defined in vocabulary but never bound or composed.
```

### 6.4 JUnit XML

For CI systems that consume JUnit format:

```xml
<testsuites name="honest-check">
  <testsuite name="src/pipelines/user.py" failures="1">
    <testcase name="HC-P001:42" classname="src/pipelines/user.py">
      <failure message="if/elif/else chain dispatches on value">
        Line 42: if role == "admin":
      </failure>
    </testcase>
  </testsuite>
</testsuites>
```

---

## 7. Rule Suppression

### 7.1 Inline suppression

A single line:
```python
if role == "admin":  # honest: ignore HC-P001
```

A block:
```python
# honest: disable HC-P001
if role == "admin":
    return admin_view(manifest)
elif role == "editor":
    return editor_view(manifest)
# honest: enable HC-P001
```

### 7.2 File-level suppression

```python
# honest: disable HC-P001, HC-P003
```

At the top of a file, applies to the entire file.

### 7.3 Configuration suppression

In `honest-check.toml`:
```toml
[rules]
disable = ["HC-P006"]
```

### 7.4 Suppression policy

Suppression is always recorded in the output with an `info` diagnostic:

```
src/pipelines/user.py:42: info
  HC-P001 suppressed by inline comment.
```

This ensures suppressions are visible in CI and do not silently accumulate.

---

## 8. Complete Rule Summary

| Rule | Severity | Firing time | Startup | Description |
|---|---|---|---|---|
| HC001 | Error | Static | ✓ | Link missing vocabulary |
| HC002 | Error | Static | ✓ | Chain type mismatch |
| HC003 | Error/Warning/Info | Construction | ✓ | Recognizer overlap |
| HC004 | Warning | Static | — | Dead vocabulary type |
| HC005 | Warning | Static | — | Unused binding |
| HC006 | Error | Construction | ✓ | Composed type references unknown base |
| HC007 | Error | Construction | ✓ | Empty chain |
| HC008 | Warning | Static | — | Impure link (framework tier) |
| HC009 | Warning | Static | — | Predicate may throw |
| HC010 | Warning | Static | — | Declared emission never produced |
| HC011 | Error | Construction | ✓ | Catch-all recognizer |
| HC-SM01 | Error | Construction | ✓ | State not in vocabulary |
| HC-SM02 | Error | Construction | ✓ | Event not in vocabulary |
| HC-SM03 | Warning | Static | — | Unreachable state |
| HC-SM04 | Warning | Static | — | Dead state |
| HC-SM05 | Error | Construction | ✓ | Initial state not in vocabulary |
| HC-P001 | Error | Static | — | if/elif/else dispatch chain |
| HC-P002 | Error | Static | — | Exception caught in non-boundary function |
| HC-P003 | Error | Static | — | Class declaration (inheritance or bare class) |
| HC-P004 | Error | Static | — | I/O inside non-boundary function |
| HC-P005 | Warning | Static | — | isinstance() in business logic |
| HC-P006 | Warning | Static | — | Cache without profiling annotation |
| HC-P007 | Warning | Static | — | Instance state in constructor |
| HC-P008 | Warning | Test | — | Gherkin step too long (honest-test) |
| HC-P009 | Warning | Test | — | Chain missing .feature file (honest-test) |
| HC-P010 | Error | Static | — | Non-serializable return value |
| HC-P011 | Error | Static | — | Framework lifecycle hook |
| HC-P013 | Error | Static | — | Unbounded database routing key |
| HC-P014 | Error | Static | — | Recognizer reused across slots |
| HC-P016 | Error | Static | — | Nonlocal closure over mutable state |
| HC-P017 | Error | Static | — | Serializer not declared as chain link |
| HC-R001 | Error | Static | — | Orphan function (no role, not reachable) |
| HC-OR001 | Error | Static | — | Orchestrator calls another orchestrator |
| HC-OR003 | Warning | Static | — | Suspected duplication between orchestrators |
| HC-A001 | Warning | Static | — | No AuthProvider registered |
| HC-A002 | Error | Static | — | Actor trusted from request input instead of the boundary |
| HC-P012 | Warning | Test | — | Excessive mocks in test (honest-test) |

**Withdrawn:** *HC-SM06 ("transition writes to undeclared state field")* has been removed. It assumed a state-machine model where a state is a record of fields and transitions are field-writing functions. The canonical model (`honest-state-architecture.md`) defines a state as an atomic name and `transition()` as a pure `(state, event) → next_state` lookup that writes nothing — the caller persists the next state. There are no transition-written fields to police, so the rule described a model the framework does not have. honest-state §4 correctly lists only HC-SM01/02/03/04/05.

---

## 9. Conformance

### 9.1 Conformance Levels

| Level | Requirement |
|---|---|
| **Core** | All construction-time rules (HC003, HC006, HC007, HC011, HC-SM01, HC-SM02, HC-SM05) pass the conformance suite |
| **Full** | All static analysis rules pass the conformance suite |
| **Complete** | Full + LSP support + framework startup integration |

### 9.2 Conformance Suite

The conformance suite lives in the hub repo at `honest/honest-check-conformance/suite.json`. Each test case provides source code (as a string) and the expected diagnostics.

```json
{
    "id": "HC-P001-001",
    "description": "Three-branch if/elif/else dispatch chain is an error",
    "category": "HC-P001",
    "input": {
        "language": "python",
        "source": "def handle(role):\n    if role == 'admin':\n        return 1\n    elif role == 'editor':\n        return 2\n    elif role == 'viewer':\n        return 3"
    },
    "expected": {
        "diagnostics": [
            {
                "rule": "HC-P001",
                "severity": "error",
                "line": 2
            }
        ]
    }
}
```

### 9.3 Implementation Declaration

Implementations declare their conformance level in their README and package metadata:

```toml
# pyproject.toml
[tool.honest-check]
conformance = "Full"
conformance-suite-version = "1.0"
```
