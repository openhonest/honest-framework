"""Honest test for the load_config scenario (honest-check feature file).

load_config takes no arguments. It finds honest-check.toml in the nearest
ancestor directory of the working directory, reads it, and resolves the
project's declared per-rule settings into a RuleConfig map. honest-check's
one configurable rule is HC-OR003, whose single setting min_run has no
built-in default. load_config returns {} when no honest-check.toml exists or
it sets nothing, and {"HC-OR003": {"min_run": N}} when the project sets
min_run = N.

load_config is a filesystem reader whose only input is the working directory,
so each case is a real temp directory holding a real (or absent)
honest-check.toml. The probe chdir's into the directory (or a nested child,
to exercise the nearest-ancestor walk), calls the real function, compares the
returned map to the literal the scenario fixes, and restores the working
directory afterward.
"""

import os
import tempfile

from honest_check import load_config


def _run_in(toml_text, subdir):
    """Write toml_text (or nothing when None) to a fresh temp dir, chdir into
    it or a nested child, call load_config, and return the resolved map."""
    start = os.getcwd()
    with tempfile.TemporaryDirectory() as root:
        if toml_text is not None:
            with open(os.path.join(root, "honest-check.toml"), "w") as handle:
                handle.write(toml_text)
        run_from = root
        if subdir is not None:
            run_from = os.path.join(root, subdir)
            os.makedirs(run_from, exist_ok=True)
        try:
            os.chdir(run_from)
            return load_config()
        finally:
            os.chdir(start)


_CASES = [
    {
        # The literal set case: a project sets min_run = 5 under
        # [rules.HC-OR003]. load_config must return exactly this map.
        "given": {
            "toml": "[rules.HC-OR003]\nmin_run = 5\n",
            "subdir": None,
        },
        "expect": {"HC-OR003": {"min_run": 5}},
    },
    {
        # The nearest-ancestor walk: the same toml sits at the temp-dir root
        # while load_config runs from a nested child. It must still resolve to
        # the ancestor's setting.
        "given": {
            "toml": "[rules.HC-OR003]\nmin_run = 7\n",
            "subdir": os.path.join("nested", "deeper"),
        },
        "expect": {"HC-OR003": {"min_run": 7}},
    },
    {
        # Absence: a temp dir with no honest-check.toml. No default to fill in,
        # so the resolved map is empty and HC-OR003 does not fire.
        "given": {"toml": None, "subdir": None},
        "expect": {},
    },
    {
        # A honest-check.toml that sets nothing resolves to the empty map too.
        "given": {"toml": "", "subdir": None},
        "expect": {},
    },
]


def probe_load_config():
    """load_config resolves the project's honest-check.toml to the RuleConfig
    map: {"HC-OR003": {"min_run": N}} when min_run = N is set in the nearest
    ancestor, and the empty map when no toml exists or it sets nothing."""
    bad = []
    for case in _CASES:
        got = _run_in(case["given"]["toml"], case["given"]["subdir"])
        if got != case["expect"]:
            bad.append(
                f"load_config() from a dir with toml={case['given']['toml']!r} "
                f"subdir={case['given']['subdir']!r} -> {got}, "
                f"expected {case['expect']}"
            )
    return bad
