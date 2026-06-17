"""Pure tests for _browser_lint.py. No mocks: feed source strings to
`find_browser_violations` and assert on the returned violation list.
"""
from honest_test.pytest_plugin._browser_lint import (
    find_browser_violations,
    in_browser_step_roots,
)


def rules_for(source: str, **config) -> list[str]:
    """Helper: return the rule codes that fired on a snippet."""
    return [v["rule"] for v in find_browser_violations(source, "x.py", config)]


def violations_for(source: str, **config):
    return find_browser_violations(source, "x.py", config)


# --- B1: empty step body --------------------------------------------------


def test_b1_flags_pass_only_step_body():
    src = (
        "from pytest_bdd import given\n"
        "@given('a thing')\n"
        "def step_a(harness):\n"
        "    pass\n"
    )
    assert "B1" in rules_for(src)


def test_b1_flags_docstring_only_step_body():
    src = (
        "from pytest_bdd import when\n"
        "@when('something')\n"
        "def step_b(harness):\n"
        "    '''CONTRACT: should do X but never does.'''\n"
    )
    assert "B1" in rules_for(src)


def test_b1_ignores_step_with_real_body():
    src = (
        "from pytest_bdd import then\n"
        "@then('z')\n"
        "def step_c(harness):\n"
        "    do, see, _ = harness\n"
        "    assert see.is_visible('.x')\n"
    )
    assert "B1" not in rules_for(src)


def test_b1_ignores_non_step_function_with_empty_body():
    src = (
        "def helper():\n"
        "    pass\n"
    )
    assert rules_for(src) == []


def test_b1_recognises_module_qualified_decorator():
    src = (
        "import pytest_bdd\n"
        "@pytest_bdd.given('x')\n"
        "def step_q(harness):\n"
        "    pass\n"
    )
    assert "B1" in rules_for(src)


# --- B2: forbidden synthetic-event JS strings -----------------------------


def test_b2_flags_dispatchevent_string():
    src = (
        "from pytest_bdd import when\n"
        "@when('click')\n"
        "def step_c(harness, page):\n"
        "    page.evaluate(\"document.querySelector('.b').dispatchEvent(new MouseEvent('click'))\")\n"
    )
    rules = rules_for(src)
    assert "B2" in rules


def test_b2_flags_new_mouseevent_string():
    src = (
        "from pytest_bdd import when\n"
        "@when('y')\n"
        "def step_d(harness):\n"
        "    js = 'new MouseEvent(\"click\", {})'\n"
        "    print(js)\n"
    )
    assert "B2" in rules_for(src)


def test_b2_flags_evaluate_el_click():
    src = (
        "from pytest_bdd import when\n"
        "@when('y')\n"
        "def step_d(harness, page):\n"
        "    page.evaluate(\"el.click()\")\n"
    )
    assert "B2" in rules_for(src)


def test_b2_does_not_flag_clean_evaluate_for_computed_style():
    src = (
        "from pytest_bdd import then\n"
        "@then('y')\n"
        "def step_e(harness, page):\n"
        "    page.evaluate(\"getComputedStyle(document.querySelector('.x')).color\")\n"
    )
    assert rules_for(src) == []


def test_b2_does_not_flag_python_locator_click():
    src = (
        "from pytest_bdd import when\n"
        "@when('y')\n"
        "def step_f(harness, page):\n"
        "    page.locator('.btn').click()\n"
    )
    rules = rules_for(src)
    assert "B2" not in rules


# --- B3: step def missing required fixture --------------------------------


def test_b3_flags_step_without_harness_arg():
    src = (
        "from pytest_bdd import given\n"
        "@given('x')\n"
        "def step_g(page):\n"
        "    assert True\n"
    )
    assert "B3" in rules_for(src)


def test_b3_uses_configured_required_fixture_name():
    src = (
        "from pytest_bdd import given\n"
        "@given('x')\n"
        "def step_g(harness):\n"
        "    assert True\n"
    )
    assert "B3" in rules_for(src, browser_required_fixture="ui")


def test_b3_does_not_flag_when_required_fixture_present():
    src = (
        "from pytest_bdd import given\n"
        "@given('x')\n"
        "def step_h(harness, scenario_state):\n"
        "    assert True\n"
    )
    assert "B3" not in rules_for(src)


def test_b3_ignores_non_step_functions():
    src = (
        "def helper(x, y):\n"
        "    return x + y\n"
    )
    assert "B3" not in rules_for(src)


# --- B4: forbidden imports ------------------------------------------------


def test_b4_flags_from_playwright_import_page():
    src = "from playwright.sync_api import Page\n"
    assert "B4" in rules_for(src)


def test_b4_flags_import_of_auth_page_fixture():
    src = "from app.fixtures import auth_page\n"
    assert "B4" in rules_for(src)


def test_b4_respects_configured_forbidden_imports():
    src = "from app.fixtures import raw_page\n"
    rules = rules_for(src, browser_forbidden_imports=["raw_page"])
    assert "B4" in rules


def test_b4_does_not_flag_innocent_imports():
    src = (
        "import pytest\n"
        "from pytest_bdd import given, when, then\n"
    )
    assert rules_for(src) == []


# --- B5: step def grabs auth fixture via getfixturevalue -----------------


def test_b5_flags_getfixturevalue_of_auth_fixture():
    src = (
        "from pytest_bdd import when\n"
        "@when('login')\n"
        "def step_i(harness, request):\n"
        "    page = request.getfixturevalue('page')\n"
        "    assert page is not None\n"
    )
    assert "B5" in rules_for(src)


def test_b5_uses_configured_auth_fixture_name():
    src = (
        "from pytest_bdd import when\n"
        "@when('login')\n"
        "def step_j(harness, request):\n"
        "    p = request.getfixturevalue('authed_browser')\n"
        "    assert p\n"
    )
    rules = rules_for(src, browser_auth_fixture="authed_browser")
    assert "B5" in rules


def test_b5_does_not_flag_getfixturevalue_of_other_names():
    src = (
        "from pytest_bdd import when\n"
        "@when('a')\n"
        "def step_k(harness, request):\n"
        "    helper = request.getfixturevalue('scenario_state')\n"
        "    assert helper\n"
    )
    assert "B5" not in rules_for(src)


def test_b5_does_not_fire_outside_step_defs():
    src = (
        "def helper(request):\n"
        "    return request.getfixturevalue('page')\n"
    )
    assert "B5" not in rules_for(src)


# --- violations are stably ordered by (line, rule) -----------------------


def test_violations_sorted_by_line_then_rule():
    src = (
        "from playwright.sync_api import Page\n"        # line 1: B4
        "from pytest_bdd import given\n"
        "@given('x')\n"
        "def step_m(page):\n"                            # line 4: B3
        "    pass\n"                                     # line 5: (B1 on def)
    )
    vs = violations_for(src)
    lines_rules = [(v["line"], v["rule"]) for v in vs]
    assert lines_rules == sorted(lines_rules)


# --- in_browser_step_roots ------------------------------------------------


def test_in_browser_step_roots_relative_match():
    assert in_browser_step_roots(
        "tests/playwright/step_defs/test_x.py",
        ["tests/playwright/step_defs"],
    )


def test_in_browser_step_roots_absolute_match():
    assert in_browser_step_roots(
        "/home/x/proj/tests/playwright/step_defs/test_y.py",
        ["tests/playwright/step_defs"],
    )


def test_in_browser_step_roots_no_false_positive_for_sibling_prefix():
    assert not in_browser_step_roots(
        "tests/playwright/step_defs_helpers/test_x.py",
        ["tests/playwright/step_defs"],
    )


def test_in_browser_step_roots_empty_roots_returns_false():
    assert not in_browser_step_roots(
        "tests/playwright/step_defs/test_x.py", [],
    )


def test_in_browser_step_roots_multiple_roots_any_match():
    assert in_browser_step_roots(
        "tests/ui/test_x.py", ["tests/playwright", "tests/ui"],
    )
