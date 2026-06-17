from honest_page import (
    build_page_context,
    build_sse_wiring,
    check_conformance,
    declare_surface,
    theme_token_resolve,
    validate_surface_order,
    verify_bootstrap_order,
)
from honest_page.core import DECLARED_SURFACES


def test_declare_surface_builds_record():
    s = declare_surface("honest-main", "main", "body content")
    assert s["surface_id"] == "honest-main"


def test_validate_surface_order_correct():
    surfaces = [declare_surface(sid, "div", "") for sid in DECLARED_SURFACES]
    assert validate_surface_order(surfaces)


def test_validate_surface_order_wrong():
    surfaces = [declare_surface(sid, "div", "") for sid in reversed(DECLARED_SURFACES)]
    assert not validate_surface_order(surfaces)


def test_verify_bootstrap_order_strict_increase():
    steps = [{"order": i, "kind": "x", "href": ""} for i in range(5)]
    assert verify_bootstrap_order(steps)


def test_verify_bootstrap_order_out_of_order():
    steps = [{"order": 1, "kind": "x", "href": ""},
             {"order": 0, "kind": "y", "href": ""}]
    assert not verify_bootstrap_order(steps)


def test_verify_bootstrap_order_empty_ok():
    assert verify_bootstrap_order([])


def test_build_page_context_defaults():
    c = build_page_context("myapp", "Home")
    assert c["app_name"] == "myapp"
    assert c["lang"] == "en"
    assert c["theme"] == "auto"


def test_build_sse_wiring():
    w = build_sse_wiring("honest-alerts-toasts", "/alerts/stream",
                          "alert:toast", "beforeend")
    assert w["endpoint"] == "/alerts/stream"


def test_theme_token_resolve_light():
    tokens = [{"name": "ht-color-bg", "light_value": "#fff", "dark_value": "#000"}]
    assert theme_token_resolve("ht-color-bg", "light", tokens) == "#fff"
    assert theme_token_resolve("ht-color-bg", "dark", tokens) == "#000"


def test_theme_token_resolve_missing():
    assert theme_token_resolve("nope", "light", []) == ""


def test_check_conformance_core():
    html = "".join(f'<div id="{s}"></div>' for s in DECLARED_SURFACES)
    rendered = {"html": html, "request_id": "x", "status": 200}
    assert check_conformance(rendered, "core")


def test_check_conformance_fails_without_surfaces():
    rendered = {"html": "<div>empty</div>", "request_id": "x", "status": 200}
    assert not check_conformance(rendered, "core")
