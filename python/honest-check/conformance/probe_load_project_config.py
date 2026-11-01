"""load_project_config reads the nearest-ancestor honest-check.toml [check] section.

A temp honest-check.toml with [check] adoption="Boundary" exclude=["x"] resolves to
adoption 'Boundary', exclude ['x']. An empty temp dir resolves to adoption 'Declared'
(section 9.4 silence means the strictest level), exclude []. cwd restored in finally.
"""

import os
import tempfile

# toml None is the explicit absence case: no honest-check.toml, so Declared and [].
_CASES = [
    {
        "toml": '[check]\nadoption = "Boundary"\nexclude = ["x"]\n',
        "expect": {"adoption": "Boundary", "exclude": ["x"]},
    },
    {
        "toml": None,
        "expect": {"adoption": "Declared", "exclude": []},
    },
]


def probe_load_project_config():
    try:
        from honest_check import load_project_config
    except ImportError as exc:
        return [f"cannot import load_project_config: {exc}"]

    bad = []
    start = os.getcwd()
    for case in _CASES:
        with tempfile.TemporaryDirectory() as d:
            if case["toml"] is not None:
                with open(os.path.join(d, "honest-check.toml"), "w", encoding="utf-8") as fh:
                    fh.write(case["toml"])
            try:
                os.chdir(d)
                got = load_project_config()
            finally:
                os.chdir(start)
            for field, want in case["expect"].items():
                have = got.get(field) if isinstance(got, dict) else None
                if have != want:
                    bad.append(
                        f"load_project_config() with toml={case['toml']!r} "
                        f"[{field!r}] -> {have!r}, expected {want!r}"
                    )
    return bad
