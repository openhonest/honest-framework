"""Tests for the Gherkin parser. Plain pytest, one `assert` per test."""
from honest_gherkin import parse_feature


def test_empty_source_returns_empty_feature():
    f = parse_feature("", "test.feature")
    assert f == {
        "name": "",
        "description": "",
        "scenarios": [],
        "background_steps": [],
        "source_path": "test.feature",
    }


def test_feature_name_is_captured():
    src = "Feature: a simple feature\n"
    f = parse_feature(src, "t.feature")
    assert f["name"] == "a simple feature"


def test_single_scenario_with_three_steps():
    src = (
        "Feature: classify\n"
        "\n"
        "Scenario: classify an email\n"
        "  Given a vocabulary with the email recognizer\n"
        "  When I classify the token \"alice@example.com\"\n"
        "  Then the ticket is email\n"
    )
    f = parse_feature(src, "t.feature")
    assert len(f["scenarios"]) == 1
    assert f["scenarios"][0]["name"] == "classify an email"
    assert [s["kind"] for s in f["scenarios"][0]["steps"]] == ["given", "when", "then"]


def test_step_text_has_keyword_stripped():
    src = (
        "Feature: x\n"
        "Scenario: y\n"
        "  Given a vocabulary\n"
    )
    f = parse_feature(src, "t.feature")
    assert f["scenarios"][0]["steps"][0]["text"] == "a vocabulary"


def test_and_but_steps_are_preserved():
    src = (
        "Feature: x\n"
        "Scenario: y\n"
        "  Given a precondition\n"
        "  And another precondition\n"
        "  But not a third\n"
    )
    f = parse_feature(src, "t.feature")
    kinds = [s["kind"] for s in f["scenarios"][0]["steps"]]
    assert kinds == ["given", "and", "but"]


def test_tags_attach_to_next_scenario():
    src = (
        "Feature: x\n"
        "@smoke @fast\n"
        "Scenario: y\n"
        "  Given a condition\n"
    )
    f = parse_feature(src, "t.feature")
    assert f["scenarios"][0]["tags"] == ["@smoke", "@fast"]


def test_comments_and_blanks_are_ignored():
    src = (
        "# top comment\n"
        "\n"
        "Feature: x\n"
        "# another\n"
        "\n"
        "Scenario: y\n"
        "  Given a condition\n"
    )
    f = parse_feature(src, "t.feature")
    assert f["name"] == "x"
    assert len(f["scenarios"]) == 1


def test_description_lines_captured_after_feature():
    src = (
        "Feature: x\n"
        "  A multi-line\n"
        "  description.\n"
        "\n"
        "Scenario: y\n"
        "  Given a condition\n"
    )
    f = parse_feature(src, "t.feature")
    assert "A multi-line" in f["description"]
    assert "description." in f["description"]


def test_step_outside_scenario_raises():
    src = (
        "Feature: x\n"
        "  Given a stray step\n"
    )
    import pytest
    with pytest.raises(ValueError, match="bad_feature_syntax"):
        parse_feature(src, "t.feature")
