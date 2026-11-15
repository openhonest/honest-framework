"""Conformance probe for honest-check's features_vocabulary.

Scenario (specs/features/honest-check.feature, Scenario: features_vocabulary):
    Given ctx: CheckContext
    When features_vocabulary is called
    Then it returns the feature-flag vocabulary this module declares - each flag name
    mapped to the set of states its FEATURES[flag]["states"] set names - read only from
    a module-scope FEATURES dict literal (HC-HF001, HC-HF002).

The probe parses each module with the real honest-parse grammar, builds a CheckContext,
and compares the returned flag->states map against the literal the scenario fixes. State
collections are normalized to sets, since the scenario names "the set of states".
"""

import honest_parse

_POPULATED = (
    'FEATURES = {\n'
    '    "dark_mode": {"states": {"on", "off"}},\n'
    '    "beta": {"states": {"enabled", "disabled"}},\n'
    '}\n'
)

_ABSENT = 'x = 1\ndef f():\n    return x\n'

# Each case: a module source and the flag->set(states) map it declares.
_CASES = [
    {"src": _POPULATED, "expect": {"dark_mode": {"on", "off"}, "beta": {"enabled", "disabled"}}},
    {"src": _ABSENT, "expect": {}},  # no module-scope FEATURES dict -> empty vocabulary
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
        "path": "feature.py",
        "rule_config": {"HC-OR003": {"min_run": 3}},
    }


def _norm(mapping):
    return {flag: set(states) for flag, states in mapping.items()}


def probe_features_vocabulary():
    """A module-scope FEATURES dict declares each flag's states; a module without one declares the empty vocabulary (HC-HF001/HC-HF002)."""
    try:
        from honest_check import features_vocabulary
    except ImportError as exc:
        return [f"cannot import features_vocabulary: {exc}"]

    bad = []
    for case in _CASES:
        ctx = _ctx(case["src"])
        try:
            got = features_vocabulary(ctx)
            got_norm = _norm(got)
        except Exception as exc:
            bad.append(f"features_vocabulary(<module>) raised {exc!r} for {case['src']!r}")
            continue
        if got_norm != case["expect"]:
            bad.append(f"features_vocabulary(<module>) -> {got_norm!r}, expected {case['expect']!r}")
    return bad
