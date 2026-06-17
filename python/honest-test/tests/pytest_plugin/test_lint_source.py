"""Pure tests for _lint_source.py (M2.4 silent-default lint).

No mocks. Source strings in, violation lists out.
"""
from honest_test.pytest_plugin._lint_source import (
    ALLOW_MARKER,
    find_silent_default_violations,
    render_silent_default_report,
)


def violations_of(
    source: str,
    params=None,
    values=None,
    exempt=None,
    path: str = "apps/x.py",
):
    return find_silent_default_violations(
        source,
        path,
        params=params if params is not None else ["user_id", "workspace_id"],
        values=values if values is not None else ["", "None"],
        exempt=exempt if exempt is not None else [],
    )


# --- opt-in: empty params = no-op ----------------------------------------


def test_no_params_means_no_violations():
    src = "def f(user_id: str = ''): pass\n"
    assert find_silent_default_violations(src, "x.py", [], ["", "None"], []) == []


# --- empty-string default ------------------------------------------------


def test_flags_empty_string_default():
    src = "def f(user_id: str = ''): pass\n"
    v = violations_of(src)
    assert len(v) == 1
    assert v[0]["param_name"] == "user_id"
    assert v[0]["default_text"] == "''"


def test_flags_double_quoted_empty_string():
    # ast normalises to single quotes, but the source uses double
    src = 'def f(user_id: str = ""): pass\n'
    v = violations_of(src)
    assert len(v) == 1


def test_does_not_flag_nonempty_string():
    src = "def f(user_id: str = 'anon'): pass\n"
    assert violations_of(src) == []


# --- None default --------------------------------------------------------


def test_flags_none_default():
    src = "def f(pool=None): pass\n"
    v = violations_of(src, params=["pool"])
    assert len(v) == 1
    assert v[0]["default_text"] == "None"


def test_does_not_flag_numeric_default():
    src = "def f(pool=0): pass\n"
    assert violations_of(src, params=["pool"]) == []


def test_does_not_flag_when_no_default():
    src = "def f(user_id: str): pass\n"
    assert violations_of(src) == []


# --- multi-arg signatures ------------------------------------------------


def test_flags_multiple_params_on_one_function():
    src = (
        "def f(card_id: str, "
        "user_id: str = '', "
        "workspace_id: str = ''): pass\n"
    )
    v = violations_of(src)
    assert len(v) == 2
    names = {row["param_name"] for row in v}
    assert names == {"user_id", "workspace_id"}


def test_only_flags_params_in_param_list():
    src = (
        "def f(other_id: str = '', "
        "user_id: str = ''): pass\n"
    )
    v = violations_of(src, params=["user_id"])
    assert len(v) == 1
    assert v[0]["param_name"] == "user_id"


# --- escape hatches ------------------------------------------------------


def test_line_marker_clears_violation():
    src = (
        f"def f(user_id: str = ''):  {ALLOW_MARKER}\n"
        "    pass\n"
    )
    assert violations_of(src) == []


def test_exempt_list_clears_violation():
    src = "def get_user_workspaces(user_id: str = ''): pass\n"
    exempt = ["apps/x.py:get_user_workspaces"]
    assert violations_of(src, exempt=exempt) == []


def test_exempt_match_is_exact_not_substring():
    src = "def my_get_user_workspaces(user_id: str = ''): pass\n"
    exempt = ["apps/x.py:get_user_workspaces"]  # different fn name
    assert len(violations_of(src, exempt=exempt)) == 1


# --- class methods (acceptance #6) --------------------------------------


def test_flags_class_method():
    src = (
        "class Repo:\n"
        "    def get(self, user_id: str = ''):\n"
        "        pass\n"
    )
    v = violations_of(src)
    assert len(v) == 1
    assert v[0]["function_name"] == "get"


def test_flags_nested_function():
    src = (
        "def outer():\n"
        "    def inner(user_id: str = ''):\n"
        "        pass\n"
        "    return inner\n"
    )
    v = violations_of(src)
    assert len(v) == 1
    assert v[0]["function_name"] == "inner"


# --- argument shapes -----------------------------------------------------


def test_flags_async_function():
    src = "async def f(user_id: str = ''): pass\n"
    v = violations_of(src)
    assert len(v) == 1


def test_flags_kwonly_arg():
    src = "def f(*, user_id: str = ''): pass\n"
    v = violations_of(src)
    assert len(v) == 1


def test_flags_posonly_arg():
    src = "def f(user_id: str = '', /): pass\n"
    v = violations_of(src)
    assert len(v) == 1


def test_ignores_required_param_without_default():
    src = "def f(user_id: str, *, workspace_id: str): pass\n"
    assert violations_of(src) == []


# --- record shape --------------------------------------------------------


def test_violation_carries_full_record():
    src = (
        "def f(card_id: str, user_id: str = ''):\n"
        "    pass\n"
    )
    v = violations_of(src)[0]
    assert v["path"] == "apps/x.py"
    assert v["line"] == 1
    assert v["function_name"] == "f"
    assert v["param_name"] == "user_id"
    assert v["default_text"] == "''"
    assert "card_id" in v["signature"]
    assert "user_id" in v["signature"]


# --- render --------------------------------------------------------------


def test_render_empty_violations_returns_empty_string():
    assert render_silent_default_report([]) == ""


def test_render_groups_violations_by_function():
    violations = [
        {
            "path": "apps/x.py",
            "line": 5,
            "function_name": "get_thing",
            "param_name": "user_id",
            "default_text": "''",
            "signature": "get_thing(user_id: str = '', workspace_id: str = '')",
        },
        {
            "path": "apps/x.py",
            "line": 5,
            "function_name": "get_thing",
            "param_name": "workspace_id",
            "default_text": "''",
            "signature": "get_thing(user_id: str = '', workspace_id: str = '')",
        },
    ]
    out = render_silent_default_report(violations)
    assert "honest_test silent-default lint" in out
    assert "apps/x.py:5" in out
    assert "get_thing" in out
    assert "user_id: empty-string default" in out
    assert "workspace_id: empty-string default" in out
    # signature line should appear once even though we have 2 violations
    assert out.count("get_thing(user_id") == 1


def test_render_includes_totals():
    v = {
        "path": "apps/x.py",
        "line": 5,
        "function_name": "f",
        "param_name": "user_id",
        "default_text": "''",
        "signature": "f(user_id: str = '')",
    }
    out = render_silent_default_report([v])
    assert "Total: 1 violations across 1 files" in out


# --- custom values list (the user-configurable bit) ----------------------


def test_custom_value_text_match():
    # Not a sentinel — falls back to ast.unparse equality
    src = "def f(user_id: str = 'TBD'): pass\n"
    v = violations_of(src, values=["'TBD'"])
    assert len(v) == 1


def test_default_values_can_disable_none_match():
    src = "def f(pool=None): pass\n"
    # Only flag empty string; None default should pass
    assert violations_of(src, params=["pool"], values=[""]) == []
