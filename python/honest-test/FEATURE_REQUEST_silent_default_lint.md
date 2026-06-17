# Feature Request: M2.4 — production-code lint for silent-default correctness-critical parameters

> Extends the M2 pytest-plugin layer with a third collection-time lint
> targeting **production source files** (not test files), rejecting
> empty-string and None defaults on parameter names that are
> correctness-critical and must never be optional.

## Problem

Consumer projects routinely declare parameters like:

```python
async def get_card_by_id(card_id: str, workspace_id: str, user_id: str = "") -> Optional[dict]:
    ...
```

A function downstream then does:

```python
pool = await get_project_pool(user_id, workspace_id)
```

The type checker waves the bad call site through because `user_id=""` is "valid" per the signature. The real failure happens three frames deep when `get_project_pool` raises `ValueError: requires both args`, with a stack that points at the pool helper, not at the missing-kwarg call site.

In the multicardz consumer alone, a grep surfaced:

- **~28** function signatures with `user_id: str = ""`
- **~16** function signatures with `workspace_id: str = ""`
- **~9** call sites that drop the kwarg, causing ~10 honest-test scenarios to fail with stacks one frame too deep to debug from

The pattern is broadly applicable wherever a correctness-critical identifier (user, workspace, tenant, pool, connection) is passed through a service layer.

## Why this belongs in honest-test

M2.2 already runs a collection-time AST lint that rejects mock-family imports in test files. The mechanism — collection-time scan, per-line escape comment, configurable allow-list — is exactly the shape needed here. The new lint targets a different scan set (production source instead of tests), but shares everything else.

Catching this at pytest collection time means:

- Every test run fails before any test runs, the moment the violating signature is added.
- A developer can't "I'll fix it later" — the suite refuses to start.
- The signal is identical to the mock-family lint developers already see.

The complementary layer (git pre-commit hook) is project-local. The plugin version is portable across every honest-test-aware consumer.

## Proposed configuration

```toml
[tool.honest_test]

# Existing M2 keys ...
lint = true
source_roots = ["apps"]
exclude_patterns = ["routes/", "templates/"]

# NEW (M2.4):
silent_default_params = ["user_id", "workspace_id", "pool", "db", "connection"]
silent_default_values = ["", "None"]   # also accept the unquoted literal "None"
silent_default_exempt = [               # opt-out per (file, fn) for legitimate sentinels
    "apps/shared/repositories/card_repository.py:invalidate_tag_ids_cache",
    "apps/user/routes/workspaces_api.py:get_user_workspaces",
]
```

Defaults if the keys are omitted:

- `silent_default_params`: empty list → lint is OFF (opt-in).
- `silent_default_values`: `["", "None"]`.
- `silent_default_exempt`: empty list.

## Detection logic

`pytest_plugin/_lint_source.py` (new module):

1. At `pytest_collection_finish` (or earlier — same hook as existing lint), walk every `.py` file under each `source_roots[i]` minus `exclude_patterns`.
2. AST-parse each file. For every top-level **and class-method** `FunctionDef` / `AsyncFunctionDef`:
   - Zip `node.args.args` (or `node.args.posonlyargs` / `kwonlyargs`) with the trailing tail of `node.args.defaults`.
   - For each `(arg, default)` pair where `arg.arg in silent_default_params`:
     - Render the default as text (`ast.unparse(default)` on 3.9+).
     - If the rendered text is in `silent_default_values`, this is a violation.
     - Skip if the line has the marker comment `# allow-empty-default-required`.
     - Skip if `f"{rel_path}:{fn_name}"` is in `silent_default_exempt`.
3. Aggregate violations. Emit at `pytest_terminal_summary` and (if `silent_default_fail_under_count = true`, default true) exit non-zero before tests run.

The line-marker check is the same shape as the existing `# allow-card-tags-heresy-mention` / `# allow-per-test-context` escape valves the multicardz pre-commit hook already uses.

## Error output

A single block in the terminal summary, matching the existing `honest contract coverage` and `honest summary` style:

```
honest_test silent-default lint
===============================
apps/shared/services/group_storage.py:99
  get_group_by_id(group_id, user_id: str = "", workspace_id: str = "")
    user_id: empty-string default on correctness-critical parameter
    workspace_id: empty-string default on correctness-critical parameter
apps/shared/repositories/card_repository.py:160
  add_tag_to_card(card_id, workspace_id, tag_id, user_id: str = "")
    user_id: empty-string default on correctness-critical parameter

Total: 44 violations across 2 files
```

## Fixes the lint enforces

The lint forces one of two outcomes for every violation:

1. **Drop the default**:
   ```python
   # before
   async def get_group_by_id(group_id: str, user_id: str = "", workspace_id: str = "") -> ...:

   # after — required-without-default. Missing kwarg → TypeError at call site.
   async def get_group_by_id(group_id: str, *, user_id: str, workspace_id: str) -> ...:
   ```

2. **Mark the sentinel** (only when both-empty / None is a deliberate semantic):
   ```python
   def invalidate_tag_ids_cache(  # allow-empty-default-required
       user_id: str = "",
       workspace_id: str = "",
   ) -> None:
       """Drop the cached card_id → tag_ids map for one workspace, or all."""
       if user_id and workspace_id:
           ...drop one entry...
       else:
           ...drop all...
   ```

## Acceptance criteria

1. With `silent_default_params = ["user_id"]` and a test file containing `def f(user_id: str = ""): ...` in a source root, the plugin emits one violation and exits non-zero.
2. Adding `# allow-empty-default-required` to the violating `def` line clears the violation.
3. Adding the (file, fn) string to `silent_default_exempt` clears the violation.
4. With `silent_default_params = []` (default), the lint is a no-op.
5. The lint respects `exclude_patterns` from the existing M2 config — files under `routes/` are not scanned when `routes/` is excluded.
6. Class methods are scanned, not just top-level functions.
7. The lint scans **production source** under `source_roots`, NOT test files. Test files are still subject to the existing M2.2 mock-family lint.
8. Honest-code dogfooding: the plugin itself ships honest tests for this lint, with no test relying on mocks.

## Open questions

- **Should `None` be configurable separately from the empty-string set?** Pool / connection params default to `None` semantically; identity params default to `""`. The same lint catches both, but a user may want different param lists for each default value. Proposal: keep one list (`silent_default_params`) and let each project pick the union; if granularity becomes useful, split later.

- **Should the lint check `Optional[T] = None` shapes too?** A parameter declared `Optional[str]` with default `None` is a stronger signal that None is meaningful; the type checker enforces that. But the silent-failure mode is the same: a downstream call assumes the value is non-None. Proposal: include `Optional[...]` and `T | None` shapes by default; let the user opt out via `silent_default_values` configuration.

- **Should the lint also catch the inverse — required parameters that should default**? No. That's a code-style preference, not a correctness rule.

- **kwargs-only marker (`*`) requirement?** Some consumers may want to additionally require that user_id / workspace_id be keyword-only (`*, user_id: str`). That's a strictly tighter rule; could be a follow-up `silent_default_require_kwonly = true` flag. Out of scope for M2.4.

## Out of scope for M2.4

- Whole-file typed-parameter inference (use mypy / pyright for that).
- Cross-function call-site validation that callers ARE passing the kwargs. That requires a call-graph walk; possible future M3 work.
- Automatic refactoring (e.g., a `--fix` mode that drops defaults). Risky; the violations should be reviewed individually.

## Reference implementation in the consumer

The multicardz project shipped a git pre-commit hook with equivalent semantics. The bash hook pattern, after fixing a macOS-grep character-class quirk:

```bash
SILENT_DEFAULT_PATTERNS=(
    "(user_id|workspace_id) *: *[^=]* *= *\"\""
    "(user_id|workspace_id) *: *[^=]* *= *''"
    "\\bpool *: *[^=]* *= *None"
)
# escape marker: # allow-empty-default-required
```

The Python AST equivalent inside honest-test is preferred because it:

- Handles multi-line `def` signatures naturally (the bash regex catches single-line; multi-line works only because each param lands on its own line and the regex matches per-line).
- Detects nested class methods and lambdas in a way that regex grep can't.
- Reports the function name alongside the file:line.
- Is portable across grep dialects (BSD / GNU / busybox).
