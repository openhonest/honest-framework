"""Pure tests for _count.py."""
from honest_test.pytest_plugin._count import (
    count_contracts,
    parse_contract_id,
    render_contract_summary,
)
from honest_test.pytest_plugin._config import DEFAULTS


def test_parse_contract_id_plain():
    assert parse_contract_id("tests/foo.py::test_bar") == (
        "tests/foo.py", "test_bar",
    )


def test_parse_contract_id_parametrize():
    assert parse_contract_id("tests/foo.py::test_bar[1-2]") == (
        "tests/foo.py", "test_bar",
    )


def test_parse_contract_id_class_nested():
    assert parse_contract_id("tests/foo.py::TestX::test_bar[a]") == (
        "tests/foo.py", "test_bar",
    )


def test_count_contracts_collapses_parametrize():
    nodeids = [
        "tests/a.py::test_x[1]",
        "tests/a.py::test_x[2]",
        "tests/a.py::test_x[3]",
        "tests/a.py::test_y",
    ]
    stats = count_contracts(nodeids)
    assert stats["pytest_items"] == 4
    assert stats["distinct_contracts"] == 2
    assert stats["parametrize_ratio"] == 2.0


def test_count_contracts_distinct_modules_are_distinct_contracts():
    nodeids = [
        "tests/a.py::test_x",
        "tests/b.py::test_x",
    ]
    stats = count_contracts(nodeids)
    assert stats["distinct_contracts"] == 2


def test_count_contracts_empty():
    stats = count_contracts([])
    assert stats["pytest_items"] == 0
    assert stats["distinct_contracts"] == 0
    assert stats["parametrize_ratio"] == 0.0


def test_render_contract_summary_full():
    stats = {
        "pytest_items": 100,
        "distinct_contracts": 25,
        "parametrize_ratio": 4.0,
    }
    out = render_contract_summary(stats, DEFAULTS)
    assert "honest summary" in out
    assert "pytest items collected:  100" in out
    assert "distinct contracts:        25" in out
    assert "parametrize ratio:        4.0x" in out


def test_render_contract_summary_drops_disabled_lines():
    stats = {
        "pytest_items": 100,
        "distinct_contracts": 25,
        "parametrize_ratio": 4.0,
    }
    config = dict(DEFAULTS)
    config["report_pytest_items"] = False
    out = render_contract_summary(stats, config)
    assert "pytest items collected" not in out
    assert "distinct contracts" in out
