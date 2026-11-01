"""check_paths pulls each file and folds every file's diagnostics into one list.

A path to a .py declaring a class yields a list carrying an HC-P003 finding; a path
to a clean .py yields the empty list. Real temp files, no mock.
"""

import os
import tempfile

# want_rule None is the explicit clean case: an all-clean tree folds to [].
_CASES = [
    {"source": "class Report:\n    pass\n", "want_rule": "HC-P003"},
    {"source": "x = 1\n", "want_rule": None},
]


def probe_check_paths():
    try:
        from honest_check import check_paths
    except ImportError as exc:
        return [f"cannot import check_paths: {exc}"]

    bad = []
    for case in _CASES:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "source.py")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(case["source"])
            got = check_paths([path])
            if not isinstance(got, list):
                bad.append(f"check_paths([{path!r}]) -> {got!r}, expected a list")
                continue
            rule_ids = [diag.get("rule_id") for diag in got]
            if case["want_rule"] is None:
                if got != []:
                    bad.append(
                        f"check_paths([{path!r}]) over clean source -> {got!r}, expected []"
                    )
            elif case["want_rule"] not in rule_ids:
                bad.append(
                    f"check_paths([{path!r}]) -> rule_ids {rule_ids}, "
                    f"expected one to be {case['want_rule']!r}"
                )
    return bad
