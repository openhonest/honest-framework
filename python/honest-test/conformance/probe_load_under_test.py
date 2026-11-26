# scenario: load_under_test imports each module to obtain its live declarations
# inherits: hd=python/honest-test/honest-test.hd::load_under_test -> feature=specs/features/honest-test.feature::load_under_test imports each module to obtain its live declarations

"""The module loader returns its complete live declaration surface."""

import os
import shutil
import tempfile
from pathlib import Path

from honest_test import load_under_test

_FIXTURES = Path(__file__).parent / "fixtures"

_LIVE_FIELDS = (
    "vocabularies",
    "bindings",
    "links",
    "link_declarations",
    "chains",
    "chain_declarations",
    "machines",
    "schemas",
    "components",
    "providers",
    "gates",
)


def probe_load_under_test():
    """load_under_test returns a LiveModules record with exactly the declared fields and the live objects found in the source directory."""
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

        if set(got) != set(_LIVE_FIELDS):
            bad.append(f"LiveModules fields should be {sorted(_LIVE_FIELDS)}, got {sorted(got)}")

        for field in _LIVE_FIELDS:
            if field not in got:
                bad.append(f"LiveModules is missing the {field!r} field: keys {sorted(got)}")
            elif not isinstance(got[field], list):
                bad.append(f"LiveModules.{field} is {type(got[field]).__name__}, expected a list")
            elif got[field] != []:
                bad.append(f"LiveModules.{field} = {got[field]!r}, expected [] for a declaration-free module")
    finally:
        shutil.rmtree(src_dir)

    declared = load_under_test(str(_FIXTURES / "adopter_honest"))
    expected = {"vocabularies": 1, "links": 2, "link_declarations": 2}
    actual = {field: len(declared[field]) for field in expected}
    if actual != expected:
        bad.append(f"adopter live declarations should be {expected}, got {actual}")

    with tempfile.TemporaryDirectory() as source_dir:
        (Path(source_dir) / "ordered_chain.py").write_text(
            "from honest_type import binding, chain, link, vocabulary\n"
            "first_vocab = vocabulary({'action': {'read'}})\n"
            "second_vocab = vocabulary({'action': {'write'}})\n"
            "first_binding = binding({'action': 'requested'})\n"
            "second_binding = binding({'action': 'processed'})\n"
            "@link(accepts=first_vocab, binds=first_binding)\n"
            "def first(manifest): return first_vocab, first_binding\n"
            "@link(accepts=second_vocab, binds=second_binding)\n"
            "def second(manifest): return second_vocab, second_binding\n"
            "pipeline = chain(first, second)\n",
            encoding="utf-8",
        )
        ordered = load_under_test(source_dir)
    contracts = ordered["chain_declarations"]
    if len(contracts) != 1:
        bad.append(f"one live chain declaration was expected, got {contracts!r}")
    else:
        contract = contracts[0]
        names = [link.__name__ for link in contract["links"]]
        if names != ["first", "second"]:
            bad.append(f"the chain order must be first and then second, got {names!r}")
        else:
            upstream_vocab, upstream_binding = contract["links"][0]({})
            if contract["vocab"] is not upstream_vocab or contract["binding"] is not upstream_binding:
                bad.append("the chain declaration must carry the upstream link's vocabulary and binding")

    return bad


def run():
    failures = probe_load_under_test()
    for message in failures:
        print(f"FAIL load_under_test: {message}")
    print(f"load_under_test probe: {'PASS' if not failures else str(len(failures)) + ' failed'}")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)
