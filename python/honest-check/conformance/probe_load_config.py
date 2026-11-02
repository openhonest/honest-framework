"""load_config resolves the nearest-ancestor honest-check.toml [rules] into a RuleConfig.

A temp dir whose honest-check.toml sets [rules.HC-OR003] min_run = 3 resolves to
{"HC-OR003": {"min_run": 3}}; an empty temp dir resolves to {} because min_run has
no default to fill in. A honest-check.toml that sits in an ancestor of the working
directory is found by walking up, not only when it sits in the working directory
itself. The working directory is the real input; cwd is restored in finally.
"""

import os
import tempfile

# toml None is the explicit absence case: no honest-check.toml, so the empty map.
_CASES = [
    {
        "toml": "[rules.HC-OR003]\nmin_run = 3\n",
        "expect": {"HC-OR003": {"min_run": 3}},
    },
    {
        "toml": None,
        "expect": {},
    },
    # A honest-check.toml that exists but sets no HC-OR003 min_run resolves to the
    # empty map: there is nothing to fill in, and min_run has no default.
    {
        "toml": "[rules]\n",
        "expect": {},
    },
]


def probe_load_config():
    try:
        from honest_check import load_config
    except ImportError as exc:
        return [f"cannot import load_config: {exc}"]

    bad = []
    start = os.getcwd()
    for case in _CASES:
        with tempfile.TemporaryDirectory() as d:
            if case["toml"] is not None:
                with open(os.path.join(d, "honest-check.toml"), "w", encoding="utf-8") as fh:
                    fh.write(case["toml"])
            try:
                os.chdir(d)
                got = load_config()
            finally:
                os.chdir(start)
            if got != case["expect"]:
                bad.append(
                    f"load_config() in dir with toml={case['toml']!r} -> {got!r}, "
                    f"expected {case['expect']!r}"
                )

    # The ancestor walk: honest-check.toml sits one directory above the working
    # directory. find_toml climbs from the child, past a directory with no toml, to
    # read the one above it. A walk that stopped at the first directory would miss
    # it and resolve to the empty map.
    with tempfile.TemporaryDirectory() as root:
        with open(os.path.join(root, "honest-check.toml"), "w", encoding="utf-8") as fh:
            fh.write("[rules.HC-OR003]\nmin_run = 7\n")
        child = os.path.join(root, "child")
        os.mkdir(child)
        try:
            os.chdir(child)
            got = load_config()
        finally:
            os.chdir(start)
        if got != {"HC-OR003": {"min_run": 7}}:
            bad.append(
                f"load_config() from a child directory -> {got!r}, expected the "
                f"ancestor honest-check.toml's {{'HC-OR003': {{'min_run': 7}}}}"
            )
    return bad
