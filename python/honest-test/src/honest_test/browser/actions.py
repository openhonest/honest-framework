"""Real-input facade for browser tests.

The only methods exposed are ones that route through the browser's real
input pipeline (CDP mouse / keyboard). `evaluate`, DOM-method invocation,
and Event-object construction are deliberately absent: if a test needs
something not here, the user cannot actually do it either.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page


class UserAction:
    def __init__(self, page: Page) -> None:
        self._page = page

    def click(self, selector: str) -> None:
        self._page.locator(selector).click()

    def hover(self, selector: str) -> None:
        self._page.locator(selector).hover()

    def drag(self, source: str, target: str) -> None:
        self._page.locator(source).drag_to(self._page.locator(target))

    def drag_and_hold(
        self,
        source: str,
        dx: int,
        dy: int,
        hold_ms: int,
    ) -> None:
        """Press on source, drag past the 5px threshold by (dx, dy), hold
        without further movement for hold_ms, release. Use this when the
        test must observe state during the drag (highlights, ghost, etc.).
        """
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
        """Sequential keydown/keypress/keyup per char."""
        self._page.locator(selector).type(text)

    def paste(self, selector: str, text: str) -> None:
        """Programmatic clipboard paste. Acceptable alternative to typing
        when typing is too slow or triggers debounced handlers.
        """
        self._page.locator(selector).focus()
        self._page.keyboard.insert_text(text)

    def press(self, key: str) -> None:
        self._page.keyboard.press(key)
