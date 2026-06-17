"""Browser-test fixtures: `clean_page` and `harness`.

`clean_page` is a Playwright `page` with console / requestfailed
listeners already installed. Use it in the consumer's auth fixture so
errors fired during the login flow (404s, MIME refusals, uncaught
exceptions) are captured, not silently dropped.

`harness` is the single allowed entry point for browser tests. It
yields `(do, see, errors)`. The project's auth fixture (whatever
returns a logged-in Playwright Page) is resolved by name from
`[tool.honest_test].browser_auth_fixture` (default "page"). At teardown,
any captured console error / warning or failed request fails the test
even if its own assertions passed. Override per test via
`@pytest.mark.allow_console_errors` / `.allow_failed_requests`.

Recommended consumer wiring:

    @pytest.fixture
    def auth_page(clean_page):
        clean_page.goto(LOGIN_URL)
        clean_page.fill("#email", "u@x")
        clean_page.click("[type=submit]")
        return clean_page

    # pyproject.toml
    # [tool.honest_test]
    # browser_auth_fixture = "auth_page"

Chaining through `clean_page` is what makes the harness catch errors
produced during the auth flow. A consumer who points
`browser_auth_fixture` at a fixture that takes the raw `page` (or
`pytest-playwright`'s default `page`) gets reduced-safety mode: errors
fired before the harness fixture body runs are lost forever (Playwright
does not buffer past events).
"""
from __future__ import annotations

from typing import Any

import pytest

from honest_test.browser.actions import UserAction
from honest_test.browser.view import UserView


_ERRORS_ATTR = "_honest_test_errors"


def _install_listeners(page) -> dict[str, list[str]]:
    """Attach console + requestfailed listeners on `page`. Returns the
    dict the listeners write into.

    Idempotent: re-installing on a page that already has listeners is a
    bug (it would double-count events), so the caller must check
    `_ERRORS_ATTR` first.
    """
    errors: dict[str, list[str]] = {"console": [], "failed_requests": []}

    def on_console(msg) -> None:
        if msg.type in ("error", "warning"):
            errors["console"].append(f"[{msg.type}] {msg.text}")

    def on_request_failed(req) -> None:
        errors["failed_requests"].append(
            f"{req.method} {req.url}: {req.failure}"
        )

    page.on("console", on_console)
    page.on("requestfailed", on_request_failed)
    setattr(page, _ERRORS_ATTR, errors)
    return errors


@pytest.fixture
def clean_page(page):
    """A pytest-playwright `page` with honest-test listeners pre-attached.

    Chain consumer auth fixtures through this fixture so console errors
    and failed requests during login are caught by the harness teardown:

        @pytest.fixture
        def auth_page(clean_page):
            clean_page.goto(LOGIN_URL)
            ...
            return clean_page
    """
    _install_listeners(page)
    yield page


@pytest.fixture
def harness(request: pytest.FixtureRequest, pytestconfig: pytest.Config):
    """Yields (do, see, errors).

    - `do`     — UserAction (real input only)
    - `see`    — UserView (what the user sees)
    - `errors` — {"console": [...], "failed_requests": [...]}

    Resolves the project's auth fixture by name (default "page"). If
    that fixture was chained through `clean_page`, the harness picks up
    the listeners installed at navigation time. Otherwise it installs
    listeners now — reduced-safety mode: events fired before this
    moment (e.g. during login navigation) are not recoverable.
    """
    htc: dict[str, Any] = getattr(pytestconfig, "honest_test", None) or {}
    auth_fixture = htc.get("browser_auth_fixture", "page")
    page = request.getfixturevalue(auth_fixture)

    errors: dict[str, list[str]] | None = getattr(page, _ERRORS_ATTR, None)
    if errors is None:
        errors = _install_listeners(page)

    do = UserAction(page)
    see = UserView(page)
    yield do, see, errors

    allow_console = request.node.get_closest_marker("allow_console_errors")
    allow_requests = request.node.get_closest_marker("allow_failed_requests")

    if errors["console"] and not allow_console:
        joined = "\n  ".join(errors["console"][:20])
        pytest.fail(f"Console error(s) during test:\n  {joined}")
    if errors["failed_requests"] and not allow_requests:
        joined = "\n  ".join(errors["failed_requests"][:20])
        pytest.fail(f"Failed request(s) during test:\n  {joined}")
