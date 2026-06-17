"""User-visible read facade for browser tests.

Reads what the browser actually renders, not what is in the DOM.
`getComputedStyle` and Playwright's visibility check are the only sources
of truth here. There is deliberately no `count()`, no `exists()`, no
"element is present in the DOM" shortcut: DOM presence is not what the
user sees.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from playwright.sync_api import Page


class UserView:
    def __init__(self, page: Page) -> None:
        self._page = page

    def computed(self, selector: str, prop: str) -> Any:
        """getComputedStyle(el)[prop]: what the browser actually renders."""
        return self._page.evaluate(
            "({sel, prop}) => { const el = document.querySelector(sel); "
            "return el ? getComputedStyle(el)[prop] : null; }",
            {"sel": selector, "prop": prop},
        )

    def is_visible(self, selector: str) -> bool:
        """Playwright's visibility check: exists + non-zero size + not hidden."""
        return self._page.locator(selector).first.is_visible()

    def outline_color(self, selector: str) -> str:
        return self.computed(selector, "outlineColor")

    def background_color(self, selector: str) -> str:
        return self.computed(selector, "backgroundColor")

    def screenshot(self, path: str) -> None:
        self._page.screenshot(path=path)

    def expect_visible(self, selector: str) -> Any:
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
