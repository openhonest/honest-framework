# honest-test — M2 spec: pytest-plugin layer

> Status: proposal. M1 (`verify_purity`, `verify_mutation`, `verify_idempotency`,
> `classification_suite`, `adversarial_neighbors`) is shipped. M2 adds three
> pytest-plugin features that grade an entire downstream test suite.

## Why M2 exists

M1 gives you a primitive: "verify this property of this one function over
this bounded vocabulary." You call it from inside a `def test_*` and pytest
reports pass/fail.

M2 is orthogonal. It does not test functions. It grades **test suites**.
The motivating problem: pytest reports `2,299 tests passed` for a project
where the honest contract count is closer to 500. Two reasons:

- `@pytest.mark.parametrize(..., [v1, ..., v20])` fans 1 test into 20 items.
- Agents and humans both fragment a single contract across many `test_*`
  variants (`test_x_empty`, `test_x_one`, `test_x_many`) that prove the
  same fact with different inputs.

That inflation matters because "we have N tests" is the wrong question.
The right question is **"how many function-signature contracts are
pinned, and are any of those tests dishonest?"** M2 answers both, at
pytest run time, with no rewrite of existing tests.

## Definitions

**Function-signature contract.** A claim of the form

> for inputs satisfying P, `fn` returns outputs satisfying Q (or raises E).

One contract may be verified by one or many pytest items.

**Honest test.** A pytest item that:

1. calls a function-under-test (FUT) reachable from the project's source roots,
2. contains at least one explicit `assert` (never bare `assert True` or a
   plain call with no assertion),
3. does not import or use `unittest.mock`, `MagicMock`, `Mock`, `AsyncMock`,
   `@patch`, `pytest_mock`, or `monkeypatch.setattr` against a production
   module global.

**Dishonest test.** Any pytest item that fails the honest criteria.

## What M2 ships

Three features, independently togglable. All exposed as pytest hooks via
a single entry point.

### M2.1 — Contract counting

A pytest report that distinguishes pytest-items-collected from
distinct-contracts. A contract is identified by `(test_module, top-level def
name)`. Parametrize cases share one identity.

Terminal output, appended to the standard pytest summary:

```
honest summary
==============
pytest items collected:  2299
distinct contracts:        487
parametrize ratio:        4.7x
```

Configurable in `pyproject.toml`:

```toml
[tool.honest_test]
report_contracts = true   # default
report_pytest_items = true  # default
```

### M2.2 — Dishonesty lint at collection time

A `pytest_collectstart` hook that AST-walks each test file before items
are produced. The file's collection fails with a clear, single-line error
naming the offending import or call site if it contains any of:

- `from unittest import mock` or `from unittest.mock import …`
- `import unittest.mock`
- `from pytest_mock import …`
- `@patch(…)` or `@patch.object(…)` decorator
- `MagicMock(`, `Mock(`, `AsyncMock(` call sites
- `monkeypatch.setattr(<string targeting a production module>, …)`

False-positive boundary (must NOT reject):

- `tmp_path` / `tmp_path_factory` (real filesystem)
- `types.SimpleNamespace(...)` (real namespace object, not a mock)
- Snapshot/restore of module globals via direct attribute access
  (e.g. `saved = module.X; module.X = test_value; …; module.X = saved`).
  This is honest substitution, not mocking. The lint targets the
  mock-family identifiers, not the substitution technique.

Configurable:

```toml
[tool.honest_test]
lint = true               # default false to make adoption non-breaking
lint_exempt = [           # opt-in escape valve for legacy modules
  "tests/legacy/*.py",
]
```

A project introducing M2 to a mature codebase can set `lint = true` only
after migrating off mocks; the exempt list documents intentional debt.

### M2.3 — Contract coverage

For each public function in the configured source roots, the plugin
reports whether at least one collected test pins its contract.

A function is **pinned** iff there exists a collected pytest item where
both of these hold:

- the function's name is referenced in the test's module (by import,
  attribute access, or unqualified call),
- the test's body (AST) contains at least one explicit `assert`.

This is a coarse signal — it doesn't verify that the assert is about the
function's return value, only that the function is referenced from a
test that asserts something. It is a strict superset of "actually
untested," which is the metric that matters for closing the
honest-coverage gap.

Terminal output:

```
honest contract coverage
========================
apps/shared/services/
  multi_tier_errors.py         18 pinned /  18 functions (100%)
  tag_discovery_service.py      5 pinned /   5 functions (100%)
  tag_space_narrower.py         4 pinned /   4 functions (100%)
apps/admin/
  data.py                       9 pinned /  31 functions ( 29%)
apps/public/services/
  ab_test_service.py            3 pinned /  11 functions ( 27%)

Total: 487 pinned / 835 functions (58%)
```

Configurable:

```toml
[tool.honest_test]
source_roots = ["apps"]
exclude_patterns = ["routes/", "templates/"]
private_functions = "skip"   # "skip" (default) | "include"
coverage_min = 80
coverage_fail_under = true   # exit non-zero if below threshold
```

## What M2 explicitly does NOT do

- It is **not a replacement for `def test_*`** syntax. Existing pytest tests
  stay verbatim.
- It is **not a property-based generator.** Hypothesis fills that niche.
  M1's `enumerate_set_members` is the framework's own bounded-vocabulary
  enumerator; that's the property-generation story for honest-framework.
- It is **not a line-coverage replacement.** coverage.py answers "which
  lines ran?" — orthogonal to "which function-signatures are pinned?"
  Both are useful; both should run.
- It is **not a mock-bypass.** A test file with mocks fails collection.
  There is no soft-warning mode.
- It does **not** enforce a particular assertion style — `assert ==`,
  `pytest.raises`, `pytest.approx` all count.

## Integration with M1

M1 tests look like:

```python
from honest_test import verify_purity

def test_add_is_pure():
    suite = verify_purity(add, {"a": ["1", "2"], "b": ["3", "4"]})
    assert suite["total_failed"] == 0
```

M2 sees this and counts it as:

- 1 pytest item (good — no parametrize inflation)
- 1 contract (the test_add_is_pure contract)
- references `add` → if `add` is in a configured source root, `add` becomes
  pinned in the coverage report.

So M1 produces exactly the shape M2 expects. The two compose naturally.

## Implementation sketch

Add a subpackage under the existing source tree:

```
src/honest_test/
  __init__.py        (already exports M1 primitives — leave alone)
  enumerate.py       (M1)
  suites.py          (M1)
  types.py           (M1)
  pytest_plugin/
    __init__.py      (registers hooks)
    _count.py        (M2.1: pytest_collection_finish)
    _lint.py         (M2.2: pytest_collectstart, AST scanner)
    _coverage.py     (M2.3: pytest_sessionstart + collection_modifyitems
                     + terminal_summary)
    _config.py       (read [tool.honest_test] from pyproject.toml)
```

Entry point:

```toml
[project.entry-points.pytest11]
honest_test = "honest_test.pytest_plugin"
```

Pure functions everywhere honest-framework's `HC-P003` allows. State that
must persist across hooks is held in `session.config.honest_test` as a
TypedDict, not a class instance.

## Acceptance criteria

1. The plugin loads on a vanilla `pytest >= 8.0` project with no
   modifications to existing test files.
2. With M2.1 enabled, the terminal output gains the `honest summary`
   block. Numbers verified by sampling: for the multicardz project, the
   contract count should be within ±5% of a manual `def test_*`-occurrence
   grep across `tests/pure/` + `tests/repository/`.
3. With M2.2 enabled, a synthetic test file containing
   `from unittest.mock import MagicMock` fails collection with an error
   message including the file path, line number, and offending import.
4. With M2.3 enabled and `source_roots = ["apps"]`, the terminal summary
   gains the `honest contract coverage` block. The number of pinned
   functions matches a hand-audit on at least one module.
5. Each feature is independently togglable. Disabling all three reduces
   the plugin to a no-op (no terminal output beyond the entry-point load
   message).
6. M2 itself ships with honest tests in `tests/pytest_plugin/` that pass
   the M2.2 lint when run on themselves — the plugin dogfoods the
   enforcement.

## Open questions

- **Production-module heuristic for `monkeypatch.setattr` rejection.** The
  AST sees `monkeypatch.setattr("apps.x.y", value)` as a string literal
  first arg. We can reject any string starting with a configured source
  root prefix. That catches the common case but misses
  `monkeypatch.setattr(apps.x, "y", value)` (attribute-access form).
  Proposal: reject both. Tracked as `OPEN-1`.

- **Coarse vs. classified coverage.** M2.3 currently reports a flat
  pinned/not-pinned. Should it inherit the
  PURE / PURE-WITH-FAKE / BOUNDARY / FRAMEWORK classification from a
  separate honest-framework module (analogous to `honest-check`)?
  Proposal: out of scope for M2; add in M3 if needed. Tracked as
  `OPEN-2`.

- **Integration-test escape valve.** Some projects keep `tests/playwright/`
  or `tests/e2e/` separate. Should those be opt-out of honest counting?
  Proposal: yes, via `tool.honest_test.exclude_patterns` (already
  configurable). The plugin uses the exclude set for both lint and
  coverage. Tracked as `OPEN-3`.

- **Async test functions.** Treated identically to sync. No special
  handling needed. Tracked closed.

- **Contract identity across modules.** If two test files both define
  `def test_user_creation()`, are they one contract or two? Two — the
  identity is `(test_module, top-level def name)`. Already covered in
  the M2.1 definition above; restating for clarity.

## Out of scope for M2 (parking lot)

- Per-test contract-classification labels (could be a future
  `@honest_contract(kind="PURE")` decorator and an `honest-check` rule).
- Cross-project rollup (multi-repo honest-coverage dashboard).
- IDE integration (VSCode/PyCharm surfaces the per-function pinning
  state inline). honest-page already does the static-rendering work; this
  would just need a JSON exporter.
- A `honest-test migrate` CLI that takes an existing test suite and
  surfaces every mock so a project can plan removal before flipping the
  lint on.
