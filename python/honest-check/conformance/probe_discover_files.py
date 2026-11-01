"""discover_files walks the paths and keeps only recognized, non-excluded source files.

A tree with a.py, b.txt and sub/c.py yields the two .py files and not b.txt; an
exclude glob '*a.py' drops a.py. Real temp tree, no mock.
"""

import os
import tempfile


def _build_tree(root):
    with open(os.path.join(root, "a.py"), "w", encoding="utf-8") as fh:
        fh.write("x = 1\n")
    with open(os.path.join(root, "b.txt"), "w", encoding="utf-8") as fh:
        fh.write("not source\n")
    sub = os.path.join(root, "sub")
    os.mkdir(sub)
    with open(os.path.join(sub, "c.py"), "w", encoding="utf-8") as fh:
        fh.write("y = 2\n")


# want: basenames that must appear. absent: basenames that must not.
_CASES = [
    {"exclude": [], "want": {"a.py", "c.py"}, "absent": {"b.txt"}},
    {"exclude": ["*a.py"], "want": {"c.py"}, "absent": {"a.py", "b.txt"}},
]


def probe_discover_files():
    try:
        from honest_check import discover_files
    except ImportError as exc:
        return [f"cannot import discover_files: {exc}"]

    bad = []
    for case in _CASES:
        with tempfile.TemporaryDirectory() as root:
            _build_tree(root)
            got = discover_files([root], case["exclude"])
            if not isinstance(got, list):
                bad.append(f"discover_files([{root!r}], {case['exclude']}) -> {got!r}, expected a list")
                continue
            bases = {os.path.basename(p) for p in got}
            missing = case["want"] - bases
            if missing:
                bad.append(
                    f"discover_files exclude={case['exclude']} -> basenames {sorted(bases)}, "
                    f"missing {sorted(missing)}"
                )
            present = case["absent"] & bases
            if present:
                bad.append(
                    f"discover_files exclude={case['exclude']} -> basenames {sorted(bases)}, "
                    f"should not contain {sorted(present)}"
                )
    return bad
