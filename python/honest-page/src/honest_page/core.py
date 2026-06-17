"""Pure page primitives."""
from __future__ import annotations

from typing import TypedDict


# Declared surfaces. honest-page expects these six to exist at runtime.
DECLARED_SURFACES = (
    "honest-header",
    "honest-main",
    "honest-footer",
    "honest-alerts-banners",
    "honest-alerts-toasts",
    "honest-alerts-modal",
)


class Surface(TypedDict):
    surface_id: str
    element: str
    purpose: str


class PageContext(TypedDict):
    app_name: str
    page_title: str
    lang: str
    theme: str
    request_id: str


class BootstrapStep(TypedDict):
    order: int
    kind: str
    href: str


class SSEWiring(TypedDict):
    surface_id: str
    endpoint: str
    swap_event: str
    swap_mode: str


class ThemeToken(TypedDict):
    name: str
    light_value: str
    dark_value: str


class RenderedPage(TypedDict):
    html: str
    request_id: str
    status: int


# --- Constructors + validators --------------------------------------------


def declare_surface(surface_id: str, element: str, purpose: str) -> Surface:
    return Surface(surface_id=surface_id, element=element, purpose=purpose)


def validate_surface_order(surfaces: list[Surface]) -> bool:
    """Verify the declared surface order matches DECLARED_SURFACES."""
    names = [s["surface_id"] for s in surfaces]
    return tuple(names) == DECLARED_SURFACES


def verify_bootstrap_order(steps: list[BootstrapStep]) -> bool:
    """Each step's `order` must be strictly increasing."""
    if not steps:
        return True
    orders = [s["order"] for s in steps]
    return all(orders[i] < orders[i + 1] for i in range(len(orders) - 1))


def build_page_context(
    app_name: str,
    page_title: str,
    lang: str = "en",
    theme: str = "auto",
    request_id: str = "",
) -> PageContext:
    return PageContext(
        app_name=app_name, page_title=page_title, lang=lang,
        theme=theme, request_id=request_id,
    )


def build_sse_wiring(
    surface_id: str, endpoint: str, swap_event: str, swap_mode: str,
) -> SSEWiring:
    return SSEWiring(
        surface_id=surface_id, endpoint=endpoint,
        swap_event=swap_event, swap_mode=swap_mode,
    )


def theme_token_resolve(
    name: str, mode: str, tokens: list[ThemeToken],
) -> str:
    """Dict-lookup resolution: find the token by name, return the value for mode."""
    by_name = {t["name"]: t for t in tokens}
    token = by_name.get(name)
    if token is None:
        return ""
    return token["dark_value"] if mode == "dark" else token["light_value"]


# Conformance levels: how strict to be when checking a rendered page.
_CONFORMANCE_CHECKS: dict[str, list[str]] = {
    "core":     ["has_surfaces"],
    "full":     ["has_surfaces", "has_sse_wiring"],
    "complete": ["has_surfaces", "has_sse_wiring", "has_theme_tokens"],
}


def check_conformance(rendered: RenderedPage, level: str = "core") -> bool:
    """Cheap heuristic check against the rendered HTML body."""
    html = rendered.get("html", "")
    checks = _CONFORMANCE_CHECKS.get(level, [])
    for check in checks:
        if not _CONFORMANCE_PREDICATES[check](html):
            return False
    return True


def _has_surfaces(html: str) -> bool:
    return all(f'id="{s}"' in html for s in DECLARED_SURFACES)


def _has_sse_wiring(html: str) -> bool:
    return "ht-sse-endpoint" in html


def _has_theme_tokens(html: str) -> bool:
    return "ht-color-bg-primary" in html


_CONFORMANCE_PREDICATES = {
    "has_surfaces":     _has_surfaces,
    "has_sse_wiring":   _has_sse_wiring,
    "has_theme_tokens": _has_theme_tokens,
}
