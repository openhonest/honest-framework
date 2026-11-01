"""honest-check conformance: check_paths folds per-file diagnostics in path order.

The check_paths scenario in honest-check.feature: the orchestrator pulls the
resolved rule_config once with load_config, reads each path with read_source,
runs check_source over each file under that one config, and folds every file's
diagnostics into one flat list in the order the paths were given. An empty path
list returns [].

This probe calls the real check_paths against real temp source files. No stand-in.
A Diagnostic is a TypedDict, so a finding is a dict and rule_id is a dict key.
"""

import os
import tempfile

from honest_check import check_paths

# One honest-framework source file whose only content is a class declaration.
# check_source already runs HC-P003 (class declaration), so check_paths over this
# single file must return a non-empty list carrying a Diagnostic with that rule_id.
_CLASS_SOURCE = "class Foo:\n    pass\n"


def _write(tmpdir, name, source):
    """Write one real source file and return its path, the input check_paths takes."""
    path = os.path.join(tmpdir, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(source)
    return path


def _rule_ids(diagnostics):
    """The rule_id of each finding, in list order."""
    return [d["rule_id"] for d in diagnostics]


def probe_check_paths():
    """check_paths reads each path, checks it under one config, and folds the findings in path order; an empty path list returns []."""
    bad = []
    with tempfile.TemporaryDirectory() as tmpdir:
        class_a = _write(tmpdir, "a_foo.py", _CLASS_SOURCE)
        class_b = _write(tmpdir, "b_bar.py", _CLASS_SOURCE)

        # The absence case: no paths means no files to check, so the folded list is empty.
        empty = check_paths([])
        if empty != []:
            bad.append(f"check_paths([]) -> {empty!r}, expected []")

        # The literal case a [] stub cannot pass: one class file must produce a
        # finding whose rule_id is HC-P003 (the class-declaration rule).
        one = check_paths([class_a])
        one_ids = _rule_ids(one)
        if "HC-P003" not in one_ids:
            bad.append(
                f"check_paths([class file]) -> rule_ids {one_ids!r}, "
                f"expected HC-P003 present"
            )

        # Order case: diagnostics fold in the order the paths were given, so every
        # finding stamped with the first path precedes every finding stamped with
        # the second. source_location is file:line:col, so it names the path.
        two = check_paths([class_a, class_b])
        a_positions = [i for i, d in enumerate(two) if class_a in d["source_location"]]
        b_positions = [i for i, d in enumerate(two) if class_b in d["source_location"]]
        if not a_positions:
            bad.append(
                f"check_paths([a, b]) -> no finding stamped with the first path "
                f"{class_a!r}; source_locations {[d['source_location'] for d in two]!r}"
            )
        if not b_positions:
            bad.append(
                f"check_paths([a, b]) -> no finding stamped with the second path "
                f"{class_b!r}; source_locations {[d['source_location'] for d in two]!r}"
            )
        if a_positions and b_positions and max(a_positions) >= min(b_positions):
            bad.append(
                f"check_paths([a, b]) folded out of path order: first-path findings "
                f"at {a_positions}, second-path findings at {b_positions}"
            )
    return bad


if __name__ == "__main__":
    failures = probe_check_paths()
    if failures:
        for line in failures:
            print(line)
        raise SystemExit(1)
    print("probe_check_paths: ok")
