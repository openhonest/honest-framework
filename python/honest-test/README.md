# honest-test

Exhaustive-verification harness for the Honest Framework. Three layers:

- **M1** (`honest_test`) — bounded-vocabulary verification of pure
  functions. Enumerate the Cartesian product of declared inputs, verify
  purity, mutation, idempotency, classification, adversarial neighbors.
- **M2** (`honest_test.pytest_plugin`) — collection-time grading of a
  downstream pytest suite: contract counting, mock lint, honest-coverage,
  silent-default lint.
- **M3** (`honest_test.browser`, optional) — Playwright facade and
  collection-time lint for pytest-bdd step defs. Real input only,
  user-visible assertions only, auto-fail on console / failed requests.

The plugin layer (M2 / M3) registers itself as a `pytest11` entry point,
so it loads automatically once the package is installed. Everything is
opt-in through `[tool.honest_test]`; nothing fires until you configure it.

## Install

```bash
uv add honest-test                     # M1 + M2
uv add 'honest-test[browser]'          # adds M3 (Playwright)
```

Python 3.12 or newer. Pytest 8.0 or newer.

## M1: verify a pure function exhaustively

```python
from honest_test import verify_purity

def normalise(s: str) -> str:
    return s.strip().lower()

def test_normalise_is_pure():
    suite = verify_purity(
        normalise,
        {"s": ["", " ", "X", "  Foo  "]},
        runs=3,
    )
    assert suite["total_failed"] == 0
```

`verify_purity` calls `normalise` three times per input and pins that
every output is identical. Sister primitives:

- `verify_mutation(fn, vocab)` — fn must not mutate its inputs.
- `verify_idempotency(fn, vocab)` — `fn(fn(x)) == fn(x)`.
- `classification_suite(fn, vocab)` — every input is classified
  (no rejection).
- `adversarial_neighbors(fn, vocab)` — near-miss inputs are rejected.

All take the same `vocab` shape: `{argname: [string, string, ...]}`.
`enumerate_set_members(vocab)` exposes the Cartesian product directly.

## M2: grade your existing pytest suite

```toml
# pyproject.toml
[tool.honest_test]
report_contracts = true
report_pytest_items = true

lint = true                          # M2.2: reject mock-family tests
lint_exempt = ["tests/legacy/*"]

source_roots = ["apps"]              # M2.3: honest-coverage
exclude_patterns = ["routes/"]
coverage_min = 80
coverage_fail_under = true

silent_default_params = [            # M2.4: production-source lint
    "user_id", "workspace_id", "pool",
]
```

Run `pytest` as usual. The terminal output gains:

```
honest summary
==============
pytest items collected:  2299
distinct contracts:        487
parametrize ratio:        4.7x

honest contract coverage
========================
apps/shared/services/
  multi_tier_errors.py     18 pinned /  18 functions (100%)
  tag_discovery_service.py  5 pinned /   5 functions (100%)
...
Total: 487 pinned / 835 functions (58%)
```

If `lint = true` and a test file imports `unittest.mock`, collection
fails with the file path and line number. If `silent_default_params` is
non-empty and a production module declares `user_id: str = ""`,
collection fails with the offending signature.

See [SPEC-M2.md](SPEC-M2.md) for the full feature matrix, the false-positive
boundary (e.g. `monkeypatch.setattr` on a module global is rejected;
`saved = mod.X; mod.X = ...; mod.X = saved` is fine), and the rationale.

## M3: lock browser tests into real input and visible assertions

```toml
[tool.honest_test]
browser_step_roots = ["tests/playwright/step_defs"]
browser_auth_fixture = "auth_page"   # see "Consumer wiring" below
# defaults are usually enough:
# browser_required_fixture = "harness"
# browser_forbidden_imports = ["Page", "auth_page"]
```

**Consumer wiring.** Define `auth_page` to chain through `clean_page`
so login-flow console errors and failed requests are captured (the
harness's teardown can only see events fired *after* its listener
attaches; chaining moves that attach point upstream of navigation):

```python
# tests/playwright/conftest.py
import pytest
from honest_test.browser import clean_page, harness   # noqa: F401


@pytest.fixture
def auth_page(clean_page):
    clean_page.goto("http://localhost:8000/login")
    clean_page.fill("#email", "u@example.com")
    clean_page.fill("#password", "secret")
    clean_page.click("[type=submit]")
    return clean_page
```

A consumer who skips this and points `browser_auth_fixture` at the raw
`page` still gets a working harness, just in reduced-safety mode:
errors fired during login navigation are unrecoverable. See
[SPEC-M3-browser.md](SPEC-M3-browser.md#m31--browser-test-harness-honest-testbrowser)
for the rationale.

```python
# tests/playwright/step_defs/test_drag.py
from pytest_bdd import given, when, then, scenarios

scenarios("../features/drag.feature")


@given("the board has a card")
def given_card(harness):
    do, see, _errors = harness
    do.click("[data-testid='add-card']")
    assert see.is_visible("[data-card-id]")


@when("the user drags it onto the second column")
def when_drag(harness):
    do, see, _errors = harness
    do.drag("[data-card-id]", "[data-column-index='1']")


@then("the card shows in the second column")
def then_landed(harness):
    do, see, _errors = harness
    see.expect_visible("[data-column-index='1'] [data-card-id]")
    see.expect_background_color("[data-card-id]", "rgb(255, 255, 255)")
```

What the harness enforces:

- `do` is `UserAction`. It has `click`, `hover`, `drag`,
  `drag_and_hold`, `type_text`, `paste`, `press`. No `evaluate`. No
  Event constructors. Real CDP input only.
- `see` is `UserView`. It reads `getComputedStyle`, visibility, and
  takes screenshots. No `count()`, no `exists()`, no DOM-presence
  shortcuts. Pin what the user sees.
- `errors` is `{"console": [...], "failed_requests": [...]}`. At
  teardown, if either list is non-empty the test fails even if its
  own assertions passed. Override per-test with
  `@pytest.mark.allow_console_errors` / `.allow_failed_requests`.

What the collection-time lint enforces (rules B1-B5):

| rule | rejects |
|---|---|
| B1 | `@given/@when/@then` step def with `pass` or docstring-only body |
| B2 | string literal containing `dispatchEvent(`, `new MouseEvent(`, `.click(`, etc. — synthetic-event patterns inside `evaluate(...)` |
| B3 | step def whose argument list lacks the configured `browser_required_fixture` (default `harness`) |
| B4 | file-level import of `Page`, `auth_page`, or any other configured forbidden symbol |
| B5 | `request.getfixturevalue("page")` (or whichever the auth fixture is) inside a step def — a back-door around the harness |

A violation prints as:

```
honest_test browser_lint: tests/playwright/step_defs/test_drag.py:12: [B1] step def 'step_drag_card' has empty body: ...
```

The lint scopes itself by file path: only files under
`browser_step_roots` are scanned. Set the list to `[]` (the default) to
turn the lint off without uninstalling the extra.

See [SPEC-M3-browser.md](SPEC-M3-browser.md) for the full rule table,
the motivating-incident postmortem, the configuration reference, and
the integration story with M2.

## Project layout

```
src/honest_test/
  __init__.py             # M1 exports
  enumerate.py            # M1: Cartesian-product enumeration
  suites.py               # M1: verify_purity, verify_mutation, ...
  types.py                # M1: TestSuite, TestResult, ...
  pytest_plugin/
    __init__.py           # registers pytest11 hooks
    _config.py            # reads [tool.honest_test]
    _count.py             # M2.1
    _lint.py              # M2.2
    _coverage.py          # M2.3
    _lint_source.py       # M2.4
    _browser_lint.py      # M3.2 (B1-B5)
    _types.py             # internal TypedDicts
  browser/                # M3 (optional: requires the [browser] extra)
    __init__.py
    actions.py            # UserAction
    view.py               # UserView
    fixtures.py           # the harness fixture
```

## Honest Code conformance

`honest-test` follows the Honest Framework's architectural rules:

- No classes for business logic. `UserAction` and `UserView` are thin
  facades over Playwright; they hold a single `_page` reference and
  exist solely to restrict the API surface.
- I/O at the boundary. `_lint.py`, `_lint_source.py`, `_browser_lint.py`,
  and `_count.py` expose pure functions; the pytest hook layer is the
  only place that reads files or writes to the terminal.
- Dict-lookup polymorphism over if/elif chains for sentinel matching
  (see `_lint_source._matched_sentinel`).
- TypedDicts for all internal state. No dataclasses, no Pydantic models.

The plugin tests dogfood every rule: the M2.2 lint passes on
`tests/`, the M2.4 silent-default lint passes on `tests/`, the browser
lint passes on its own test files when run with the canonical config.

## License

MIT.
