"""Honest probe for honest-check's discover_files (Scenario: discover_files).

discover_files walks the requested paths, keeps every file whose extension honest-parse
recognizes and that no exclude glob matches, recursively walks a directory, and filters
out a directory, a nonexistent path and a file of an unrecognized extension; it returns
the flat list of concrete source files. Its one side effect is reading the filesystem, so
this probe builds a real temporary directory tree — never a mock — and asserts over the
basenames discover_files returns (the returned paths may be absolute or relative, and the
walk order is unspecified, so the probe compares the set of basenames).

The recursive-walk case pins a concrete non-empty set: recognized .py/.js/.go/.ts files
across nested directories are kept, an unrecognized .txt file is dropped, and a recognized
file matching the exclude glob is dropped. The direct-file case pins a single recognized
file kept. The nonexistent-path case is the boundary empty result. A `return []` stub
passes only the nonexistent case and fails the other two.
"""
import os
import shutil
import tempfile


def _build_tree():
    root = tempfile.mkdtemp(prefix="discover_files_")
    files = {
        "keep_a.py": b"x = 1\n",
        "drop_b.txt": b"not source\n",
        "excluded_mod.py": b"x = 2\n",
        os.path.join("sub", "keep_c.js"): b"const x = 1;\n",
        os.path.join("sub", "keep_d.go"): b"package main\n",
        os.path.join("sub", "deep", "keep_e.ts"): b"const y = 2;\n",
    }
    for rel, content in files.items():
        full = os.path.join(root, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as handle:
            handle.write(content)
    return root


def probe_discover_files():
    """discover_files keeps recognized, non-excluded source files and drops the rest."""
    try:
        from honest_check import discover_files
    except ImportError as exc:
        return [f"cannot import discover_files: {exc}"]

    root = _build_tree()
    try:
        cases = [
            # Recursive walk: recognized files kept across nested dirs; .txt dropped as
            # unrecognized, excluded_mod.py dropped by the exclude glob.
            {
                "paths": [root],
                "exclude": ["*excluded*"],
                "expect": {"keep_a.py", "keep_c.js", "keep_d.go", "keep_e.ts"},
            },
            # A directly named recognized file is kept.
            {
                "paths": [os.path.join(root, "keep_a.py")],
                "exclude": [],
                "expect": {"keep_a.py"},
            },
            # Boundary: a nonexistent path is filtered out, not an error.
            {
                "paths": [os.path.join(root, "no_such_path_xyz")],
                "exclude": [],
                "expect": set(),
            },
        ]
        bad = []
        for case in cases:
            got = discover_files(paths=case["paths"], exclude=case["exclude"])
            got_names = {os.path.basename(p) for p in got}
            if got_names != case["expect"]:
                bad.append(
                    f"discover_files(paths={case['paths']}, exclude={case['exclude']}) "
                    f"-> basenames {sorted(got_names)}, expected {sorted(case['expect'])}"
                )
        return bad
    finally:
        shutil.rmtree(root, ignore_errors=True)
