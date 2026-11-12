"""Pure-function assertions for feature_gen, plus one real-I/O round trip. No mocks."""

import tempfile
from pathlib import Path

from feature_gen import (
    column_heading,
    feature_text,
    generate_feature,
    given_clause,
    group_by_column,
    invoke_lines,
    read_module,
    scenario_text,
    then_clause,
    type_text,
    when_clause,
    write_feature,
)

_STR = [{"name": "str", "args": []}]
_UNION = [{"name": "T", "args": []}, {"name": "Fault", "args": []}]
_GENERIC = [{"name": "list", "args": [[{"name": "Param", "args": []}]]}]

_FN_PURE = {
    "name": "map_types", "role": "fn", "column": 3,
    "params": [{"name": "fields", "type": _GENERIC}],
    "ret": _STR, "invokes": [], "side_effects": [], "raises": [], "note": "",
}

_FN_NO_PARAMS = {
    "name": "route_table", "role": "orchestrator", "column": 2,
    "params": [], "ret": _UNION, "invokes": ["helper"],
    "side_effects": [{"direction": "reads", "target": "database", "module": "", "door": ""}],
    "raises": [], "note": "",
}

_FN_WITH_NOTE = {
    **_FN_PURE, "name": "fold_schema", "note": "folds every pair into one schema, left to right",
}


def test_type_text_renders_a_plain_type():
    assert type_text(_STR) == "str"


def test_type_text_renders_a_union():
    assert type_text(_UNION) == "T | Fault"


def test_type_text_renders_a_generic():
    assert type_text(_GENERIC) == "list<Param>"


def test_given_clause_with_no_params():
    assert given_clause(_FN_NO_PARAMS) == "Given no input"


def test_given_clause_with_one_param():
    assert given_clause(_FN_PURE) == "Given fields: list<Param>"


def test_when_clause_names_the_function():
    assert when_clause(_FN_PURE) == "When map_types is called"


def test_then_clause_with_no_invokes_or_side_effects():
    assert then_clause(_FN_PURE) == "Then it returns str"


def test_then_clause_uses_the_hd_note_verbatim_when_present():
    assert then_clause(_FN_WITH_NOTE) == "Then folds every pair into one schema, left to right"


def test_then_clause_with_invokes_and_side_effects():
    assert then_clause(_FN_NO_PARAMS) == "Then it returns T | Fault, calling helper, with side effects: reads database"


def test_invoke_lines_empty_when_six_or_fewer():
    assert invoke_lines(_FN_NO_PARAMS) == []


def test_then_clause_drops_invokes_past_the_limit():
    many = {**_FN_PURE, "invokes": [f"callee_{i}" for i in range(7)]}
    assert then_clause(many) == "Then it returns str"


def test_invoke_lines_one_per_callee_past_the_limit():
    many = {**_FN_PURE, "invokes": [f"callee_{i}" for i in range(7)]}
    lines = invoke_lines(many)
    assert lines == [f"    And it calls callee_{i}" for i in range(7)]


def test_scenario_text_appends_invoke_lines_past_the_limit():
    many = {**_FN_PURE, "invokes": [f"callee_{i}" for i in range(7)]}
    text = scenario_text(many)
    assert "calling" not in text.splitlines()[3]
    assert text.splitlines()[-1] == "    And it calls callee_6"
    assert len(text.splitlines()) == 4 + 7


def test_scenario_text_assembles_given_when_then():
    text = scenario_text(_FN_PURE)
    assert text == (
        "  Scenario: map_types\n"
        "    Given fields: list<Param>\n"
        "    When map_types is called\n"
        "    Then it returns str"
    )


def test_column_heading_names_each_column():
    assert column_heading(1) == "# ---- the doors and readers ----"
    assert column_heading(2) == "# ---- the orchestrators ----"
    assert column_heading(3) == "# ---- the pure core ----"
    assert column_heading(4) == "# ---- the writers ----"


def test_group_by_column_preserves_order_within_a_group():
    second = {**_FN_PURE, "name": "second"}
    groups = group_by_column([_FN_PURE, second, _FN_NO_PARAMS])
    assert groups[3] == [_FN_PURE, second]
    assert groups[3][0]["name"] == "map_types"


def test_feature_text_has_a_header_and_one_block_per_column():
    text = feature_text("example", [_FN_PURE, _FN_NO_PARAMS])
    assert text.startswith("Feature: example — generated, one scenario per function (2 total)")
    assert "# ---- the pure core ----" in text
    assert "Scenario: map_types" in text
    assert "Scenario: route_table" in text


def test_read_module_faults_on_malformed_source():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "bad.hd"
        path.write_text("not valid .hd")
        fault = read_module(str(path))
        assert "what" in fault and "instead" in fault


def test_generate_feature_round_trips_a_real_hd_file():
    source = (
        "module example\n"
        "  layer tooling\n"
        "  fn double : (n: int) -> int\n"
        "  boundary_in fn run : (n: int) -> int invokes double\n"
        "  entry \"cli:__main__\" -> run\n"
    )
    with tempfile.TemporaryDirectory() as d:
        hd_path = Path(d) / "example.hd"
        feature_path = Path(d) / "example.feature"
        hd_path.write_text(source)
        result = generate_feature(str(hd_path), str(feature_path))
        assert result is True
        text = feature_path.read_text()
        assert "Scenario: double" in text
        assert "Scenario: run" in text


def test_write_feature_writes_the_file():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "out.feature"
        assert write_feature(str(path), "hello") is True
        assert path.read_text() == "hello"
