"""parse_args turns the raw argv into a resolved CliArgs, resolving absence to an
explicit bounded value at the boundary.

--format json --rule HC007 src/ gives format 'json', include_rules carrying 'HC007',
paths ['src/']. A bare src/ defaults format 'human', severity 'warning',
report_mode False. --report src/ sets report_mode True.
"""

# equals: fields that must hold an exact value. contains: a member the named list
# field must carry.
_CASES = [
    {
        "argv": ["--format", "json", "--rule", "HC007", "src/"],
        "equals": {"format": "json", "paths": ["src/"]},
        "contains": {"include_rules": "HC007"},
    },
    {
        "argv": ["src/"],
        "equals": {"format": "human", "severity": "warning", "report_mode": False},
        "contains": {},
    },
    {
        "argv": ["--report", "src/"],
        "equals": {"report_mode": True},
        "contains": {},
    },
    # An unrecognized --format word is resolved back to 'human' at the boundary
    # (section 2.1): absence and a bad value both become the explicit default.
    {
        "argv": ["--format", "xml", "src/"],
        "equals": {"format": "human", "paths": ["src/"]},
        "contains": {},
    },
]


def probe_parse_args():
    try:
        from honest_check import parse_args
    except ImportError as exc:
        return [f"cannot import parse_args: {exc}"]

    bad = []
    for case in _CASES:
        got = parse_args(case["argv"])
        for field, want in case["equals"].items():
            have = got.get(field) if isinstance(got, dict) else None
            if have != want:
                bad.append(
                    f"parse_args({case['argv']})[{field!r}] -> {have!r}, expected {want!r}"
                )
        for field, member in case["contains"].items():
            have = got.get(field, []) if isinstance(got, dict) else []
            if member not in have:
                bad.append(
                    f"parse_args({case['argv']})[{field!r}] -> {have!r}, "
                    f"expected to contain {member!r}"
                )
    return bad
