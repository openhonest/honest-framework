"""M2.1 contract counting. Pure functions; pytest hooks call them."""
from __future__ import annotations

from honest_test.pytest_plugin._types import ContractStats, HonestTestConfig


def parse_contract_id(nodeid: str) -> tuple[str, str]:
    """A contract is (test_module, top-level def name).

    pytest nodeid forms:
      "tests/foo.py::test_bar"            -> ("tests/foo.py", "test_bar")
      "tests/foo.py::test_bar[1-2]"       -> ("tests/foo.py", "test_bar")
      "tests/foo.py::TestX::test_bar[..]" -> ("tests/foo.py", "test_bar")
    """
    parts = nodeid.split("::")
    test_module = parts[0]
    leaf = parts[-1].split("[", 1)[0]
    return (test_module, leaf)


def count_contracts(nodeids: list[str]) -> ContractStats:
    """Pure: collapse parametrize cases by (module, def name)."""
    pytest_items = len(nodeids)
    contracts = {parse_contract_id(nid) for nid in nodeids}
    distinct = len(contracts)
    ratio = (pytest_items / distinct) if distinct else 0.0
    return {
        "pytest_items": pytest_items,
        "distinct_contracts": distinct,
        "parametrize_ratio": ratio,
    }


def render_contract_summary(stats: ContractStats, config: HonestTestConfig) -> str:
    """Pure: format the honest summary block per spec."""
    lines = ["honest summary", "=============="]
    if config["report_pytest_items"]:
        lines.append(f"pytest items collected:  {stats['pytest_items']}")
    if config["report_contracts"]:
        lines.append(f"distinct contracts:        {stats['distinct_contracts']}")
        lines.append(f"parametrize ratio:        {stats['parametrize_ratio']:.1f}x")
    return "\n".join(lines)
