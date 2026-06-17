"""Browser-test harness for honest-test (optional extra: honest-test[browser]).

Locks Playwright-based tests into a small, opinionated shape:

- real CDP input only (no synthetic events, no `evaluate("el.click()")`),
- user-visible assertions (computed style / visibility, not DOM presence),
- auto-fail on captured console errors / failed requests.

Importing this package requires the `browser` extra. With the extra
installed: `from honest_test.browser import UserAction, UserView, harness`.
"""
from honest_test.browser.actions import UserAction
from honest_test.browser.fixtures import clean_page, harness
from honest_test.browser.view import UserView

__all__ = ["UserAction", "UserView", "clean_page", "harness"]
