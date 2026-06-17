# honest-test — M3 spec: browser-test harness + collection-time lint

> Status: shipped (2026-05-22). M1 (`verify_purity` and friends) and M2
> (pytest plugin: contract counting, mock lint, coverage, silent-default
> lint) are prerequisites. M3 adds an optional Playwright facade and a
> sixth collection-time lint that targets pytest-bdd step def files.
> Installed via `pip install 'honest-test[browser]'`.

## Why M3 exists

M2's `feedback_grep_tests_are_not_honest_tests` rule says: a test that
passes against a buggy implementation is broken. Source-grep tests
verify words appear in a file. They are easy to make green and tell you
nothing about behavior. M2 catches one shape of this — mock-laden tests
that bypass production code paths.

M3 closes a second shape, specific to browser tests. The motivating
incident, 2026-05-22: a Playwright probe synthesised a pointer event,
read `ghosts: 1` from the DOM, and declared the drag-drop feature
"verified end-to-end." The real browser saw nothing because
`.mc-drag-ghost` had no CSS rule at all and eleven `<script defer>` tags
had been silently MIME-refused by Chrome (FastAPI returned
`application/json` for the 404 responses; Chrome refused to execute
them). The probe never captured the console. It tested
"DOM-element-presence after a synthetic event in a fresh headless
context," not "the user sees the ghost." Two different contracts. The
easier one was green.

Three failure modes the probe encoded:

1. Synthetic events bypass the real input pipeline. `dispatchEvent`,
   `new MouseEvent(...)`, and `evaluate("el.click()")` fire single
   events that skip whatever a real mouse / keyboard would have
   triggered upstream.
2. DOM presence is not user-visible. An element can be in the DOM with
   `display:none`, `opacity:0`, `0x0` size, behind a higher z-index,
   offscreen, or with no CSS rule at all. All of these pass
   "element exists" and fail "user sees."
3. A green probe that did not look at the console is a probe that did
   not look. MIME refusals, 404s on bootstrap scripts, uncaught
   exceptions: all surface in the console. Ignoring it is how a
   green probe lies.

M3 makes these three failure modes structurally impossible for any
test that opts into the harness.

## Definitions

**Browser harness.** A pytest fixture that yields a three-tuple
`(do, see, errors)`. The test reads no other browser-control object.

**Real-input action.** Mouse / keyboard input routed through the
Chromium CDP pipeline (Playwright's `locator.click()`, `mouse.down()`,
`keyboard.press()`, `keyboard.insert_text()`). Synthetic events
(`dispatchEvent`, `evaluate("el.click()")`, manual `Event` construction)
are not real-input actions.

**User-visible read.** A property the rendered page exposes:
`getComputedStyle(el)[prop]`, Playwright's `is_visible()`, or a
screenshot. DOM presence, element count, and attribute values are not
user-visible reads.

**Step def file.** A pytest-bdd module containing one or more functions
decorated with `@given`, `@when`, or `@then`. M3's lint scans files
whose path is under one of the configured `browser_step_roots`.

## What M3 ships

Two features, both opt-in through `[tool.honest_test]`.

### M3.1 — Browser-test harness (`honest-test[browser]`)

A facade over Playwright with three surfaces.

**`UserAction` (real input only):**

| method | semantics |
|---|---|
| `click(selector)` | `locator(selector).click()` |
| `hover(selector)` | `locator(selector).hover()` |
| `drag(source, target)` | `locator(source).drag_to(locator(target))` |
| `drag_and_hold(source, dx, dy, hold_ms)` | press, move past 5px threshold, hold without further movement, release |
| `type_text(selector, text)` | per-character keydown / keypress / keyup |
| `paste(selector, text)` | focus then `keyboard.insert_text` (faster than typing; preserves the focus + input-event sequence) |
| `press(key)` | `keyboard.press(key)` |

Deliberate omissions: no `evaluate`, no DOM-method invocation, no
`Event` constructors. If a step needs something not in this table, the
user cannot do it either.

**`UserView` (user-visible reads only):**

| method | reads |
|---|---|
| `computed(selector, prop)` | `getComputedStyle(el)[prop]` |
| `is_visible(selector)` | Playwright's visibility check |
| `outline_color(selector)` | computed `outlineColor` |
| `background_color(selector)` | computed `backgroundColor` |
| `screenshot(path)` | full-page screenshot |
| `expect_visible(selector)` | Playwright `expect(...).to_be_visible()` |
| `expect_outline_color(selector, color)` | asserts computed outline-color equals `color` |
| `expect_background_color(selector, color)` | asserts computed background-color equals `color` |

Deliberate omissions: no `count()`, no `exists()`, no `text_content()`.
The contract is what the user sees, not what is in the DOM.

**`harness` fixture:**

```python
@pytest.fixture
def harness(request, pytestconfig):
    """Yields (do, see, errors).

    do:     UserAction
    see:    UserView
    errors: {"console": [...], "failed_requests": [...]}
    """
```

The harness resolves the project's auth fixture by name (configurable;
default `"page"`, which is `pytest-playwright`'s stock fixture). At
teardown it **fails the test** if any console error, console warning,
or failed request was captured during the lifetime of the page. Override
per-test via:

```python
@pytest.mark.allow_console_errors
@pytest.mark.allow_failed_requests
def test_intentional_404(harness): ...
```

Both markers are auto-registered by the plugin; no `markers = [...]`
entry needed in consumer `pyproject.toml`.

**`clean_page` fixture (consumer wiring):**

The harness only catches errors captured by Playwright listeners on the
page. Playwright does not buffer console messages or failed requests
from before a listener is attached. If the consumer's auth fixture
navigates the page (login flow) before the harness fixture body runs,
any errors fired during that navigation are unrecoverable.

To close that gap, `honest_test.browser.clean_page` is a `page` fixture
with listeners pre-installed. Chain the consumer auth fixture through
it:

```python
# tests/playwright/conftest.py
from honest_test.browser import clean_page, harness   # noqa: F401

@pytest.fixture
def auth_page(clean_page):
    clean_page.goto(LOGIN_URL)
    clean_page.fill("#email", "u@example.com")
    clean_page.click("[type=submit]")
    return clean_page
```

```toml
# pyproject.toml
[tool.honest_test]
browser_auth_fixture = "auth_page"
```

If the consumer's auth fixture takes the raw `page` instead of
`clean_page`, the harness still works but operates in reduced-safety
mode: listeners are installed at harness-fixture-entry, errors from the
auth navigation are lost. The harness picks up pre-installed listeners
when present by inspecting an attribute set by `clean_page`; no extra
config is needed.

### M3.2 — Browser-test collection-time lint (B1-B5)

A `pytest_collectstart` AST scanner that fires only on files under
`browser_step_roots`. Files outside those roots are untouched. Five
rules:

| rule | trigger | reason printed |
|---|---|---|
| **B1** | `@given/@when/@then` decorator on a function whose body is `pass`, only a docstring, or both | `step def 'X' has empty body: a step that does not assert is not a contract` |
| **B2** | string literal anywhere in the file containing any of `dispatchEvent(`, `new MouseEvent(`, `new KeyboardEvent(`, `new PointerEvent(`, `new DragEvent(`, `.click(`, `.focus(` | `forbidden synthetic-event pattern '...' in a string literal: use the harness (UserAction) for real input instead` |
| **B3** | step def whose argument list does not include the required fixture (default `harness`) | `step def 'X' does not request the required 'harness' fixture: the harness must be in scope to capture console / failed-request errors` |
| **B4** | file-level `from X import Y` (or `import X.Y`) where `Y` is in `browser_forbidden_imports` (default `["Page", "auth_page"]`) | `forbidden import 'Y' ...: binding this name lets a step def bypass the harness` |
| **B5** | step def body calls `request.getfixturevalue("<auth_fixture>")` where the string equals the configured `browser_auth_fixture` (default `"page"`) | `step def 'X' grabs the auth fixture 'page' via request.getfixturevalue: that bypasses the harness's console-error capture` |

Error format on the first violation found:

```
honest_test browser_lint: tests/playwright/step_defs/test_drag.py:12: [B1] step def 'step_drag_card' has empty body: ...
```

The session aborts at collection time; no tests are run. Violations are
sorted by `(line, rule)` so the first reported is always the
earliest-line, lowest-rule pair in the file.

## Configuration reference

All keys are optional; defaults shown. M3's lint is **off** unless
`browser_step_roots` is non-empty. The harness package
(`honest_test.browser`) is importable whenever the `[browser]` extra is
installed, independently of the lint.

```toml
[tool.honest_test]
# Lint: paths whose ancestry includes any of these dirs are scanned.
# Non-empty value is the enable signal; no separate boolean toggle.
browser_step_roots = []                        # e.g. ["tests/playwright/step_defs"]

# Harness: which project fixture returns the logged-in Playwright Page.
# pytest-playwright's "page" works out of the box; override when an
# auth-aware fixture is needed.
browser_auth_fixture = "page"

# B3: every step def must declare this name as a parameter.
browser_required_fixture = "harness"

# B4: importing any of these symbols at module level fails the lint.
browser_forbidden_imports = ["Page", "auth_page"]
```

The new keys compose with M2's existing keys; both lints run in a
single `pytest_collectstart` pass and read the same `[tool.honest_test]`
table.

## Example: a complete step def

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


@then("the card is shown in the second column")
def then_landed(harness):
    do, see, _errors = harness
    see.expect_visible("[data-column-index='1'] [data-card-id]")
    see.expect_background_color(
        "[data-card-id]", "rgb(255, 255, 255)",
    )
```

A consumer running `pytest tests/playwright/` with the configuration
above gets:

- Real-input drag through Chromium's CDP (no synthetic events).
- An assertion on `background-color` that fails if `.mc-drag-ghost`
  has no CSS rule at all, because the computed value will not match.
- Automatic failure if any script returned a wrong MIME type, any
  request was refused, or any console error fired during the test.

## What M3 explicitly does NOT do

- It is **not a generic Playwright replacement.** Adopters who need
  `add_init_script`, network interception, or device emulation should
  call the underlying Playwright API directly. Those paths are not
  routed through the harness, so they do not get console capture or
  the lint surface.
- It is **not an HTML-coverage tool.** Whether every page state has a
  test is out of scope. M3 only ensures the tests that exist tell the
  truth.
- It does **not** install Playwright by default. The `[browser]` extra
  is opt-in. A project without it does not pay the dependency cost.
- It does **not** enforce a particular BDD style — `@scenario`,
  `scenarios("…")`, and parametrised features all work. M3's lint
  scopes itself by file path, not by feature-file shape.
- B2 does **not** forbid `evaluate(...)` outright. `UserView.computed`
  itself uses `evaluate` for `getComputedStyle`. The substrings in
  B2's allowlist target synthetic-event payloads, not read-side JS.

## Integration with M2

M3 reuses M2's machinery. Both lints (mock lint from M2.2 and browser
lint from M3.2) run inside a single `pytest_collectstart` callback,
reading the same `[tool.honest_test]` table on `pytestconfig`. A file's
source is read once per collection and passed to both scanners; the
file dedup set is shared.

M3.1's `harness` fixture is independent of M2's reporting features.
Contract counting (M2.1), honest-coverage (M2.3), and silent-default
lint (M2.4) all run as before; the browser-test surface adds to them
rather than replacing any of them.

## Acceptance criteria

1. `uv add 'honest-test[browser]'` (or `pip install 'honest-test[browser]'`)
   installs Playwright.
2. `from honest_test.browser import UserAction, UserView, harness`
   imports cleanly even when Playwright is not yet installed (the type
   hints use `TYPE_CHECKING`; runtime use of the harness requires the
   extra).
3. A test using the `harness` fixture against a real page yields a
   three-tuple `(UserAction, UserView, dict)`.
4. A test that produces a console error during its lifetime fails at
   teardown with the captured message in the failure output, even if
   the test's own assertions all passed. "Lifetime" means *from when
   the listener was attached* — so the consumer wiring matters: errors
   fired before the listener attaches are lost forever (Playwright does
   not buffer past events). The `clean_page` fixture exists to push the
   attach point upstream of the auth navigation; consumers wanting
   AC#4 to hold across page-load errors must chain through it.
5. A step def whose body is `pass` (or docstring only) in a file under
   `browser_step_roots` fails collection with rule B1.
6. A step def calling `page.evaluate("el.click()")` in a file under
   `browser_step_roots` fails collection with rule B2.
7. A step def that does not request the configured
   `browser_required_fixture` fails collection with rule B3.
8. Pure-function tests for all five rules pass
   (`tests/pytest_plugin/test_browser_lint.py`, 28 cases).
9. The plugin's own integration suite covers acceptance #5-#7 end-to-end
   via `pytester` (`tests/pytest_plugin/test_plugin_integration.py`,
   six browser cases).

## Resolved open questions (from the design handoff)

- **Marker registration.** The plugin auto-registers
  `allow_console_errors` and `allow_failed_requests` in
  `pytest_configure`. No `markers = [...]` entry needed in consumer
  `pyproject.toml`. Decided in favour of auto-register.

- **Enable signal.** `browser_step_roots` non-empty is the toggle.
  There is no separate `browser_lint = true` knob. Decided in favour
  of one less knob.

- **Cross-platform path matching.** `in_browser_step_roots` compares
  `Path(path).parts` as a subsequence match against
  `Path(root).parts`, so `tests/playwright/step_defs` matches
  `tests/playwright/step_defs/x.py` but not
  `tests/playwright/step_defs_helpers/x.py`. Works for both absolute
  and relative path inputs.

## Out of scope for M3 (parking lot)

- **Failed-request regex allowlist.** `@pytest.mark.allow_failed_requests`
  is currently coarse (binary on / off per test). A regex allowlist
  for tests that intentionally probe 401 or 404 endpoints is a v2
  candidate.
- **Scenario-must-hit-`see.expect_*` static check.** Resolving a
  pytest-bdd feature to its bound step defs and tracing whether any
  step makes a `see.expect_*` call would catch B1-look-alike contracts
  that hide their hollowness across multiple steps. Defers to a future
  iteration.
- **`add_init_script` / `add_script_tag` lint extension.** These
  Playwright APIs can inject JS in ways B2 does not catch. Extending
  the scan is straightforward but no consumer has needed it yet.
- **Vitest / jsdom harness.** The same shape (real-input only,
  visible-only assertions, console capture) applies to jsdom-class
  browser tests in JavaScript projects. Out of scope for the Python
  package; lives in honest-framework's TypeScript surface when that
  ships.
