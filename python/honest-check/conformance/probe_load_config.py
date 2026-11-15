"""Honest probe for honest-check's load_config (feature Scenario: load_config).

load_config takes no argument: it finds honest-check.toml in the nearest ancestor
directory of the working directory, reads it, and hands back the raw parsed
[rules] table as data (the empty dict when no [rules] section or no file exists).
Each case writes a real honest-check.toml in a real ancestor directory, changes
into a child directory, and demands the [rules] table back. The toml sits in a
parent of the working directory (not the working directory itself), so it resolves
the same whether the search includes the start directory or begins at its parent.
The populated case also carries a [check] section to pin that load_config returns
only the [rules] table, never the whole file. A `return {}` stub fails the
populated case.
"""
import os
import shutil
import tempfile

_POPULATED_TOML = (
    "[check]\n"
    'adoption = "Boundary"\n'
    "\n"
    "[rules.HC-OR003]\n"
    "min_run = 5\n"
)
# A honest-check.toml with a [check] section but no [rules] section.
_NO_RULES_TOML = "[check]\nadoption = \"Boundary\"\n"

# Each case: the honest-check.toml text (None = no file), and the [rules] table expected.
_CASES = [
    {"toml": _POPULATED_TOML, "expect": {"HC-OR003": {"min_run": 5}}},
    {"toml": _NO_RULES_TOML, "expect": {}},
    {"toml": None, "expect": {}},
]


def probe_load_config():
    """load_config returns the raw [rules] table of the nearest-ancestor honest-check.toml, or {}."""
    try:
        from honest_check import load_config
    except ImportError as exc:
        return [f"cannot import load_config: {exc}"]

    bad = []
    for case in _CASES:
        root = tempfile.mkdtemp()
        workdir = os.path.join(root, "src", "deep")
        os.makedirs(workdir)
        if case["toml"] is not None:
            config_path = os.path.join(root, "honest-check.toml")
            with open(config_path, "w", encoding="utf-8") as handle:
                handle.write(case["toml"])
        saved = os.getcwd()
        try:
            os.chdir(workdir)
            got = load_config()
        finally:
            os.chdir(saved)
            shutil.rmtree(root, ignore_errors=True)
        if got != case["expect"]:
            bad.append(
                f"load_config() under toml={case['toml']!r} -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
