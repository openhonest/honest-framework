"""load_project_config reads the nearest-ancestor honest-check.toml [check] section.

A temp honest-check.toml with [check] adoption="Boundary" exclude=["x"] resolves to
adoption 'Boundary', exclude ['x']. An empty temp dir resolves to adoption 'Declared'
(section 9.4 silence means the strictest level), exclude []. A honest-check.toml that
carries a [check] section but no adoption key, and one whose adoption names no level
the vocabulary carries, both resolve to 'Declared', because silence never buys
leniency. cwd restored in finally.
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
    # A honest-check.toml that exists and carries a [check] section but names no
    # adoption resolves to 'Declared'. This reaches the resolve expression (the
    # file is present, so the no-file early return is not taken), so the 'Declared'
    # fallback there must stand, not an empty string.
    {
        "toml": '[check]\nexclude = ["y"]\n',
        "expect": {"adoption": "Declared", "exclude": ["y"]},
    },
    # An adoption value the vocabulary does not carry also resolves to 'Declared':
    # an unrecognized level never buys a weaker setting than the strictest.
    {
        "toml": '[check]\nadoption = "Nonsense"\n',
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

    # The ancestor walk: honest-check.toml sits one directory above the working
    # directory, and declares adoption 'Boundary' and exclude ['z'], both different
    # from the no-file defaults. find_toml climbs from the child to read it. A walk
    # that stopped at the first directory would miss it and resolve to the strict
    # defaults, so 'Boundary' and ['z'] prove the climb happened.
    with tempfile.TemporaryDirectory() as root:
        with open(os.path.join(root, "honest-check.toml"), "w", encoding="utf-8") as fh:
            fh.write('[check]\nadoption = "Boundary"\nexclude = ["z"]\n')
        child = os.path.join(root, "child")
        os.mkdir(child)
        try:
            os.chdir(child)
            got = load_project_config()
        finally:
            os.chdir(start)
        for field, want in {"adoption": "Boundary", "exclude": ["z"]}.items():
            have = got.get(field) if isinstance(got, dict) else None
            if have != want:
                bad.append(
                    f"load_project_config() from a child directory [{field!r}] -> "
                    f"{have!r}, expected the ancestor toml's {want!r}"
                )
    return bad
