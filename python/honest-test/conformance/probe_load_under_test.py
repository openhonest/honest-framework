"""RED probe for honest-test.load_under_test — the module loader (.hd, section 11).

load_under_test imports each module under test and returns a LiveModules record
carrying the live vocabularies, bindings, links, link declarations, chains,
machines, schemas, components, providers and gates. Loading runs each module's own
top-level code, so it is a boundary. The probe points it at a real temporary source
directory holding one declaration-free module, so every list comes back empty, then
deletes the directory. honest-test has no code yet, so importing honest_test fails —
the correct red state.
"""

import os
import shutil
import tempfile

from honest_test import load_under_test

_LIVE_FIELDS = (
    "vocabularies",
    "bindings",
    "links",
    "link_declarations",
    "chains",
    "machines",
    "schemas",
    "components",
    "providers",
    "gates",
)


def probe_load_under_test():
    """load_under_test returns a LiveModules record whose ten fields are each a
    list, and every list is empty for a module that declares nothing."""
    bad = []

    src_dir = tempfile.mkdtemp()
    try:
        module = (
            '"""A module under test that declares no honest-type vocabularies, links,\n'
            'chains, machines, schemas, components, providers or gates."""\n'
            "\n"
            "def helper(x):\n"
            "    return x + 1\n"
        )
        with open(os.path.join(src_dir, "undertest_mod.py"), "w", encoding="utf-8") as f:
            f.write(module)

        got = load_under_test(src_dir)
        if not isinstance(got, dict):
            bad.append(f"load_under_test returned {type(got).__name__}, expected a LiveModules record")
            return bad

        for field in _LIVE_FIELDS:
            if field not in got:
                bad.append(f"LiveModules is missing the {field!r} field: keys {sorted(got)}")
            elif not isinstance(got[field], list):
                bad.append(f"LiveModules.{field} is {type(got[field]).__name__}, expected a list")
            elif got[field] != []:
                bad.append(f"LiveModules.{field} = {got[field]!r}, expected [] for a declaration-free module")
    finally:
        shutil.rmtree(src_dir)

    return bad


def run():
    failures = probe_load_under_test()
    for message in failures:
        print(f"FAIL load_under_test: {message}")
    print(f"load_under_test probe: {'PASS' if not failures else str(len(failures)) + ' failed'}")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)
