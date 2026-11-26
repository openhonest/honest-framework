# scenario: persist_write_targets
# inherits: hd=python/honest-check/honest-check.hd::persist_write_targets -> feature=specs/features/honest-check.feature::persist_write_targets
"""Conformance probe for honest-check's persist_write_targets.

Scenario (specs/features/honest-check.feature, Scenario: persist_write_targets):
    Given ctx: CheckContext
    When persist_write_targets is called
    Then it returns the dotted call targets that resolve to a honest-persist database
    writer through this file's own imports (HC-ST001).

The scenario and honest-check.hd name neither the writer functions nor the import module,
so the exact writer vocabulary is fixed one level up, in the state spec
(specs/02-code-quality/honest-state-architecture.md, section 3.1): honest-persist's
declared writers are `transaction` and `apply`, imported from `honest_persist`;
`insert`/`update`/`delete` build a Query and are not writers; a bare name no honest_persist
import binds does not count. The probe parses each file with the real honest-parse grammar
and compares the resolved targets (normalized to a set). See the GAPS note in the report:
the writer set is sourced from the state spec, not from the scenario or the .hd.
"""

import honest_parse

# Each case: a source file and the set of local call targets that resolve to a persist writer.
_CASES = [
    {
        "src": "from honest_persist import transaction\ndef save(rows):\n    transaction(rows)\n",
        "expect": {"transaction"},
    },
    {
        "src": "from honest_persist import transaction as tx\ndef save(rows):\n    tx(rows)\n",
        "expect": {"tx"},
    },
    {
        "src": "from honest_persist import apply\ndef migrate(m):\n    apply(m)\n",
        "expect": {"apply"},
    },
    {
        "src": "from honest_persist import insert\ndef save(rows):\n    insert(rows)\n",
        "expect": set(),  # insert builds a Query; it is not a writer
    },
    {
        "src": "def save(rows):\n    transaction(rows)\n",
        "expect": set(),  # bare transaction, no honest_persist import binds it
    },
    {
        "src": "from unrelated import transaction as save\ndef step(rows):\n    save(rows)\n",
        "expect": set(),
    },
    {
        "src": "import os\ndef save(rows):\n    os.getcwd()\n",
        "expect": set(),  # unrelated import and call
    },
]


def _ctx(src):
    source = src.encode("utf-8")
    tree = honest_parse.parse(source, "python")
    root = tree.root_node
    return {
        "root": root,
        "nodes": honest_parse.walk(root),
        "aliases": {},
        "roles": {},
        "source": source,
        "path": "store.py",
        "rule_config": {"HC-OR003": {"min_run": 3}},
    }


def probe_persist_write_targets():
    """Call targets bound through a honest_persist import to the declared writers transaction/apply resolve; insert, a bare unbound name, and unrelated calls do not (HC-ST001)."""
    try:
        from honest_check import persist_write_targets
    except ImportError as exc:
        return [f"cannot import persist_write_targets: {exc}"]

    bad = []
    for case in _CASES:
        ctx = _ctx(case["src"])
        try:
            got = set(persist_write_targets(ctx))
        except Exception as exc:
            bad.append(f"persist_write_targets({case['src']!r}) raised {exc!r}")
            continue
        if got != case["expect"]:
            bad.append(f"persist_write_targets({case['src']!r}) -> {got!r}, expected {case['expect']!r}")
    return bad
