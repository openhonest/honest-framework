"""Honest probe for honest-check's load_project_config (feature Scenario: load_project_config).

load_project_config takes no argument: it finds honest-check.toml in the nearest
ancestor directory of the working directory and hands back the raw parsed [check]
table as data, building no record of its own (the .hd is explicit: "neither reader
builds a record, each hands its raw section to the pure resolver"). The defaults
(exclude empty, adoption 'Declared', format_manifest empty) are resolve_project_config's
to apply, not this reader's, so the empty dict is the answer when no [check] section
or no file exists. Each case writes a real honest-check.toml in a real ancestor
directory, changes into a child directory, and demands the [check] table back. The
toml sits in a parent of the working directory, so it resolves the same whether the
search includes the start directory or begins at its parent. The populated case also
carries a [rules] section to pin that load_project_config returns only [check], and
is distinct from load_config. A `return {}` stub fails the populated case.
"""
import os
import shutil
import tempfile

_POPULATED_TOML = (
    "[rules.HC-OR003]\n"
    "min_run = 5\n"
    "\n"
    "[check]\n"
    'exclude = ["dist/*", "build/*"]\n'
    'adoption = "Boundary"\n'
    'format_manifest = "fmt/manifest.json"\n'
)
# A honest-check.toml with a [rules] section but no [check] section.
_NO_CHECK_TOML = "[rules.HC-OR003]\nmin_run = 5\n"

# Each case: the honest-check.toml text (None = no file), and the [check] table expected.
_CASES = [
    {
        "toml": _POPULATED_TOML,
        "expect": {
            "exclude": ["dist/*", "build/*"],
            "adoption": "Boundary",
            "format_manifest": "fmt/manifest.json",
        },
    },
    {"toml": _NO_CHECK_TOML, "expect": {}},
    {"toml": None, "expect": {}},
]


def probe_load_project_config():
    """load_project_config returns the raw [check] table of the nearest-ancestor honest-check.toml, or {}."""
    try:
        from honest_check import load_project_config
    except ImportError as exc:
        return [f"cannot import load_project_config: {exc}"]

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
            got = load_project_config()
        finally:
            os.chdir(saved)
            shutil.rmtree(root, ignore_errors=True)
        if got != case["expect"]:
            bad.append(
                f"load_project_config() under toml={case['toml']!r} -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
