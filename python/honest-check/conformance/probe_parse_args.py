# scenario: parse_args
# inherits: hd=python/honest-check/honest-check.hd::parse_args -> feature=specs/features/honest-check.feature::parse_args
"""Honest probe for honest-check's parse_args (feature Scenario: parse_args).

parse_args turns the raw argv vector into the resolved CliArgs record, resolving
absence at the boundary to explicit bounded values: an omitted --format becomes
'human', an omitted --severity becomes 'warning', an omitted --declaration and
--exports become the empty string, --config the empty string, --report false, and
--rule/--no-rule collect into include_rules/exclude_rules. Each case feeds a real
argv list and demands the exact CliArgs back. The defaults case pins every absence
value. The populated cases pin the flags being read. A stub that returned a fixed
record, or echoed no defaults, fails at least one case.
"""

# Each case: a real argv list, and the exact CliArgs record parse_args must return.
_CASES = [
    # Defaults: one positional path, every flag absent, resolved to its bounded value.
    {
        "argv": ["src/"],
        "expect": {
            "paths": ["src/"],
            "format": "human",
            "severity": "warning",
            "include_rules": [],
            "exclude_rules": [],
            "config_path": "",
            "report_mode": False,
            "declaration": "",
            "exports": "",
        },
    },
    # Flags set: --format, --severity, --rule and --declaration all read through.
    {
        "argv": [
            "src/",
            "--format", "json",
            "--severity", "error",
            "--rule", "HC-P001",
            "--declaration", "mod.hd",
        ],
        "expect": {
            "paths": ["src/"],
            "format": "json",
            "severity": "error",
            "include_rules": ["HC-P001"],
            "exclude_rules": [],
            "config_path": "",
            "report_mode": False,
            "declaration": "mod.hd",
            "exports": "",
        },
    },
    # Report mode changes only the report_mode field when the other flags are absent.
    {
        "argv": ["src/", "--report"],
        "expect": {
            "paths": ["src/"],
            "format": "human",
            "severity": "warning",
            "include_rules": [],
            "exclude_rules": [],
            "config_path": "",
            "report_mode": True,
            "declaration": "",
            "exports": "",
        },
    },
]


def probe_parse_args():
    """parse_args resolves a raw argv into the bounded CliArgs, defaults and all."""
    try:
        from honest_check import parse_args
    except ImportError as exc:
        return [f"cannot import parse_args: {exc}"]

    bad = []
    for case in _CASES:
        got = parse_args(argv=case["argv"])
        if got != case["expect"]:
            bad.append(
                f"parse_args({case['argv']!r}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad
