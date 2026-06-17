"""Top-level pytest configuration for honest-test's own test suite.

`pytester` is registered here (pytest requires top-level conftest for
plugin registration). It powers the integration tests under
`tests/pytest_plugin/`.
"""
pytest_plugins = ["pytester"]
