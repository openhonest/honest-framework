# Handoff: Browser-Test Enforcement for `honest-test`

**From:** Claude session in `/Users/adam/dev/multicardz` (2026-05-22)
**To:** Whoever picks this up in the honest-test repo
**Status:** Proposal, not started

---

## TL;DR

Add a Playwright browser-test harness + collection-time lint to `honest-test`, exposed as an optional extra (`honest-test[browser]`). Locks tests into:

- Real input only (no JS event synthesis)
- User-visible assertions (computed style / visibility, not DOM presence)
- Auto-fail on console errors and failed requests
- Empty-bodied `@given/@when/@then` decorators are collection-time failures

The pattern was designed in a multicardz session where I shipped a Playwright probe that read `ghosts: 1` from the DOM and declared "verified," while Adam's real browser showed nothing because `.mc-drag-ghost` had no CSS rule at all and 11 dead `<script defer>` tags were silently MIME-refused by Chrome. The probe didn't look at the console, didn't check computed style, didn't take a screenshot. Same shape as the grep-on-source test pattern: easy to make green, doesn't catch real failures.

These rules formalise the lessons. The harness implements them. The plugin enforces them.

---

## Why this belongs in honest-test (not in each project)

- The rules are universal — any project using Playwright + Honest Code principles wants them.
- The harness pattern is universal — selectors come in as method arguments; the harness itself doesn't know about any project.
- Centralised enforcement means a new forbidden-pattern rule is a one-line list edit, picked up by every project that uses the plugin.
- The auth flow IS project-specific. Each project provides its own `auth_page` (or equivalent) fixture. The harness reads its name from `[tool.honest_test]` config.

---

## Repo state when this lands on your desk

The repo currently has uncommitted work from a prior Claude session (untracked at the time of this handoff: `src/honest_test/pytest_plugin/`, `tests/pytest_plugin/`, `tests/conftest.py`, `SPEC-M2.md`, `FEATURE_REQUEST_silent_default_lint.md`, `uv.lock`).

**Address that first.** Either commit or stash that work before adding the browser-test pieces, so the diff for this feature is clean.

---

## Deliverables

### 1. `pyproject.toml` — optional extra

```toml
[project.optional-dependencies]
browser = ["pytest-playwright>=0.5"]
```

Installed by consumers with `uv add 'honest-test[browser]'`.

### 2. New package: `src/honest_test/browser/`

```
src/honest_test/browser/
  __init__.py     # re-exports UserAction, UserView, harness fixture
  actions.py      # UserAction class
  view.py         # UserView class
  fixtures.py     # `harness` pytest fixture
```

#### `actions.py` — `UserAction`

Wraps Playwright's CDP real-input API. **No `evaluate` exposed. No event synthesis.**

```python
class UserAction:
    def __init__(self, page: Page): self._page = page

    def click(self, selector: str) -> None:
        self._page.locator(selector).click()

    def hover(self, selector: str) -> None:
        self._page.locator(selector).hover()

    def drag(self, source: str, target: str) -> None:
        self._page.locator(source).drag_to(self._page.locator(target))

    def drag_and_hold(
        self, source: str, dx: int, dy: int, hold_ms: int,
    ) -> None:
        """Press on source, drag past 5px threshold by (dx, dy), hold
        without further movement for hold_ms, release. Use this when
        the test must observe state during the drag (highlights, ghost,
        etc.)."""
        box = self._page.locator(source).bounding_box()
        if not box:
            raise RuntimeError(f"{source} has no bounding box")
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        self._page.mouse.move(cx, cy)
        self._page.mouse.down()
        self._page.mouse.move(cx + dx, cy + dy, steps=3)
        self._page.wait_for_timeout(hold_ms)
        self._page.mouse.up()

    def type_text(self, selector: str, text: str) -> None:
        """Sequential keydown/keypress/keyup per char. Use when timing
        or per-key behavior matters."""
        self._page.locator(selector).type(text)

    def paste(self, selector: str, text: str) -> None:
        """Programmatic clipboard paste — acceptable alternative to
        typing per Adam's 2026-05-22 directive."""
        self._page.locator(selector).focus()
        self._page.keyboard.insert_text(text)

    def press(self, key: str) -> None:
        self._page.keyboard.press(key)
```

**Deliberate omissions:** no `evaluate`, no DOM-method invocation, no Event-object constructors. If a step def needs something not here, the answer is "the user can't actually do that" — fix the design, not the harness.

#### `view.py` — `UserView`

Read what the user actually sees.

```python
class UserView:
    def __init__(self, page: Page): self._page = page

    def computed(self, selector: str, prop: str) -> str:
        """getComputedStyle(el)[prop] — what the browser actually renders."""
        return self._page.evaluate(
            "({sel, prop}) => { const el = document.querySelector(sel); "
            "return el ? getComputedStyle(el)[prop] : null; }",
            {"sel": selector, "prop": prop},
        )

    def is_visible(self, selector: str) -> bool:
        """Playwright's is_visible: exists + non-zero size + not hidden."""
        return self._page.locator(selector).first.is_visible()

    def outline_color(self, selector: str) -> str:
        return self.computed(selector, "outlineColor")

    def background_color(self, selector: str) -> str:
        return self.computed(selector, "backgroundColor")

    def screenshot(self, path: str) -> None:
        self._page.screenshot(path=path)

    def expect_visible(self, selector: str):
        from playwright.sync_api import expect
        return expect(self._page.locator(selector)).to_be_visible()

    def expect_outline_color(self, selector: str, color: str) -> None:
        actual = self.outline_color(selector)
        assert actual == color, (
            f"{selector}: outline-color is {actual!r}, expected {color!r}"
        )

    def expect_background_color(self, selector: str, color: str) -> None:
        actual = self.background_color(selector)
        assert actual == color, (
            f"{selector}: background-color is {actual!r}, expected {color!r}"
        )
```

**Deliberate omissions:** no `count()`, no `exists()`, no shortcut for "element is in the DOM somewhere." The rule is *what does the user see*, and the DOM is not what they see.

#### `fixtures.py` — `harness` pytest fixture

Wires UserAction + UserView + console/network capture. Reads the project's auth-fixture name from config and resolves it dynamically.

```python
import pytest

from honest_test.browser.actions import UserAction
from honest_test.browser.view import UserView


@pytest.fixture
def harness(request, pytestconfig):
    """The only allowed entry point for browser tests.

    Yields (do, see, errors):
      do      — UserAction (real input)
      see     — UserView (what the user sees)
      errors  — {"console": [...], "failed_requests": [...]}

    Reads the project's auth fixture name from
    [tool.honest_test].browser_auth_fixture (default "page") and pulls
    that fixture into scope.

    At teardown: any captured console error or failed request fails
    the test, even if its own assertions passed. Override per test via
    @pytest.mark.allow_console_errors / .allow_failed_requests.
    """
    htc = getattr(pytestconfig, "honest_test", None) or {}
    auth_fixture = htc.get("browser_auth_fixture", "page")
    page = request.getfixturevalue(auth_fixture)

    errors = {"console": [], "failed_requests": []}
    def on_console(msg):
        if msg.type in ("error", "warning"):
            errors["console"].append(f"[{msg.type}] {msg.text}")
    def on_request_failed(req):
        errors["failed_requests"].append(
            f"{req.method} {req.url}: {req.failure}"
        )
    page.on("console", on_console)
    page.on("requestfailed", on_request_failed)

    do = UserAction(page)
    see = UserView(page)
    yield do, see, errors

    # Markers to opt out (use sparingly):
    allow_console = request.node.get_closest_marker("allow_console_errors")
    allow_requests = request.node.get_closest_marker("allow_failed_requests")

    if errors["console"] and not allow_console:
        msg = "Console error(s) during test:\n  " + "\n  ".join(
            errors["console"][:20]
        )
        pytest.fail(msg)
    if errors["failed_requests"] and not allow_requests:
        msg = "Failed request(s) during test:\n  " + "\n  ".join(
            errors["failed_requests"][:20]
        )
        pytest.fail(msg)
```

### 3. New module: `src/honest_test/pytest_plugin/_browser_lint.py`

Pure AST functions, no I/O. Identical pattern to existing `_lint.py` / `_lint_source.py`. Each function takes source text + config, returns a list of violations.

Rules:

| # | Rule | Trigger |
|---|---|---|
| B1 | `@given/@when/@then` decorator on empty-bodied function | function body is `pass` or docstring-only |
| B2 | Forbidden synthetic-event pattern | `dispatchEvent(`, `new MouseEvent(`, `new KeyboardEvent(`, `new PointerEvent(`, `new DragEvent(`, `evaluate(...el.click(...))`, `evaluate(...el.focus(...))`, `evaluate(...el.dispatchEvent(...))` |
| B3 | Step def signature missing required fixture | `harness` (configurable name) not in fn args |
| B4 | Step def file imports forbidden symbols | direct import of `Page` from playwright OR direct use of configured `browser_forbidden_imports` |
| B5 | Step def calls `request.getfixturevalue(<forbidden>)` | bypass attempt to grab auth fixture directly |

Each returns `{"path": str, "line": int, "rule": "B1".."B5", "reason": str}`.

### 4. Wire into `src/honest_test/pytest_plugin/__init__.py`

Add to `pytest_collectstart` (next to existing `find_violations` call):

```python
from honest_test.pytest_plugin._browser_lint import find_browser_violations

# inside pytest_collectstart, after the existing lint block:
if htc["browser_lint"] and _in_browser_step_roots(path, htc["browser_step_roots"]):
    browser_violations = find_browser_violations(
        source, path, htc,
    )
    if browser_violations:
        first = browser_violations[0]
        raise pytest.UsageError(
            f"honest_test browser_lint: "
            f"{first['path']}:{first['line']}: [{first['rule']}] {first['reason']}"
        )
```

### 5. Config keys in `src/honest_test/pytest_plugin/_config.py`

Extend `load_honest_test_config` to read:

```toml
[tool.honest_test]
browser_lint = true                              # enables B1-B5
browser_step_roots = []                          # e.g. ["tests/playwright/step_defs"]
browser_auth_fixture = "page"                    # name of the project's auth fixture
browser_required_fixture = "harness"             # rule B3 checks for this name
browser_forbidden_imports = ["Page", "auth_page"]  # rule B4 list
```

Defaults: `browser_lint=False`, all paths/lists empty. New projects opt in.

### 6. Tests in `tests/`

Pure-function tests for `_browser_lint.find_browser_violations`. Each rule gets:

- One positive case: source containing the violation → function returns it
- One negative case: clean source → function returns empty

The harness itself doesn't get automated tests in honest-test — too gnarly to test a Playwright harness without Playwright. multicardz will dogfood it; if it ships broken, the dogfooding catches it.

---

## Acceptance criteria

1. `uv add 'honest-test[browser]'` installs Playwright successfully.
2. `from honest_test.browser import UserAction, UserView, harness` works.
3. A test in a consumer project that uses the `harness` fixture and the project's `auth_page` fixture (named via config) runs against a real page and yields the three-tuple.
4. A test that produces a console error fails at teardown with the error in the message.
5. A test whose step def has empty body (just `pass`) fails at collection with rule B1.
6. A test whose step def calls `page.evaluate("el.click()")` fails at collection with rule B2.
7. A test whose step def doesn't accept `harness` (and `browser_required_fixture="harness"`) fails at collection with rule B3.
8. Pure-function tests for all five rules pass.

---

## Out of scope (do not implement here)

- **The project-side harness.** multicardz will provide its own `auth_page` fixture, `tests/playwright/features/`, `tests/playwright/step_defs/`. Not your concern.
- **Auth flows.** honest-test doesn't know how anyone logs in. It just calls `request.getfixturevalue(configured_name)`.
- **Selector vocabulary.** Selectors are arguments to methods; the harness knows none of them.
- **Scenario-must-hit-`see.expect_*` static check.** That requires resolving scenarios to step defs and tracing — harder, defer to v2.

---

## Open design questions

1. **Marker registration.** `@pytest.mark.allow_console_errors` and `.allow_failed_requests` need to be declared via `pytest_configure` or in `[tool.pytest.ini_options].markers` (in consumer pyproject.toml). The plugin could auto-register them. Recommend auto-register.

2. **`browser_lint=False` default.** Opt-in by setting `browser_lint=true`. Alternative: opt-in by setting `browser_step_roots` to non-empty (presence of paths IS the enable). Latter is one less knob. Recommend the latter.

3. **Failed-request whitelist.** What about a 401 test that intentionally hits a forbidden endpoint? The `allow_failed_requests` marker handles this, but it's coarse. v2 could allow regex patterns. Not for now.

4. **Cross-platform paths.** `_in_browser_step_roots(path, roots)` uses string `startswith`. Use `Path.relative_to` or `os.path.commonpath` so Windows back-slashes don't bite. Trivial but easy to overlook.

---

## Pointers to context

Living in the multicardz repo (read for context, don't depend on them):

- `tests/conftest.py` — existing honest-tests floor hook (recognises pytest-bdd scenario_wrapper, Playwright `expect(...).to_*`, `pytest.fail`, `_assert_*` helpers). Same shape as the new browser_lint, just for general test functions.
- `scripts/classify_grep_tests.py` — data-flow classifier I built earlier this session for separating real-render tests from grep-on-source tests. Style reference for AST-walking-with-helper-resolution.
- `scripts/diagnose_drag_pause.py` — example of the harness shape I had before factoring into a framework. Shows real CDP-input usage + console capture + render-network-spy.

Memory files (in `~/.claude/projects/-Users-adam-dev-multicardz/memory/`) that record the design principles:

- `feedback_no_synthetic_events.md` — the blanket prohibition on JS event synthesis. Option B (Playwright real-input API is fine; dispatchEvent and DOM-method invocation are not).
- `feedback_proxy_verification.md` — the "user sees ____" forcing function. Why DOM-presence is not a contract.
- `feedback_grep_tests_are_not_honest_tests.md` — the parent principle this whole effort applies to browser tests.
- `feedback_test_pins_one_contract.md` — one test, one contract, smallest claim that catches drift.

---

## What to do first

1. Resolve the uncommitted work in this repo (commit or stash).
2. Read the 4 memory files above to understand the *why*.
3. Build deliverables 1-6 in order.
4. When deliverable 8 (acceptance criteria) is green, hand control back to Adam.

The browser-side dogfooding (multicardz adopting the harness) happens in a separate session in the multicardz repo. Do not modify anything in `/Users/adam/dev/multicardz` from this session.
