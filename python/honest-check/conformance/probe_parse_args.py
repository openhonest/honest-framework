"""parse_args turns the raw argv into a resolved CliArgs, resolving absence to an
explicit bounded value at the boundary.

--format json --rule HC007 src/ gives format 'json', include_rules carrying 'HC007',
paths ['src/']. A bare src/ defaults format 'human', severity 'warning', report_mode
False, and resolves the omitted --config and --exports to the empty string. Each value
flag drives its own field, each boolean flag advances past exactly its own token, and
each positional path advances by exactly one, so two bare paths both survive. An
unrecognized or absent --format resolves to 'human'; a recognized one is kept, so the
github and junit words are not quietly rewritten to human.
"""

# equals: fields that must hold an exact value. contains: a member the named list
# field must carry.
_CASES = [
    {
        "argv": ["--format", "json", "--rule", "HC007", "src/"],
        "equals": {"format": "json", "paths": ["src/"]},
        "contains": {"include_rules": "HC007"},
    },
    # A bare path defaults every field, including the two absence-resolved strings:
    # config_path and exports both become the empty string run_check reads for base
    # mode, never an absent key.
    {
        "argv": ["src/"],
        "equals": {
            "format": "human",
            "severity": "warning",
            "report_mode": False,
            "config_path": "",
            "exports": "",
            "paths": ["src/"],
        },
        "contains": {},
    },
    # --report sets report_mode and advances past exactly its own token, so the
    # following bare path still lands in paths rather than being skipped.
    {
        "argv": ["--report", "src/"],
        "equals": {"report_mode": True, "paths": ["src/"]},
        "contains": {},
    },
    # Two bare paths each advance by one, so both survive; an over-advance would drop
    # the second.
    {
        "argv": ["a.py", "b.py"],
        "equals": {"paths": ["a.py", "b.py"]},
        "contains": {},
    },
    # --config drives config_path by its own key and value; losing either sends the
    # token to paths or to a stray field and leaves config_path at its default.
    {
        "argv": ["--config", "hc.toml", "src/"],
        "equals": {"config_path": "hc.toml", "paths": ["src/"]},
        "contains": {},
    },
    # --severity drives severity the same way; the default is 'warning', so a kept
    # 'error' proves the flag reached the field.
    {
        "argv": ["--severity", "error", "src/"],
        "equals": {"severity": "error", "paths": ["src/"]},
        "contains": {},
    },
    # --no-rule appends to exclude_rules; losing its key sends the token to paths and
    # leaves exclude_rules empty.
    {
        "argv": ["--no-rule", "HC007", "src/"],
        "equals": {"paths": ["src/"]},
        "contains": {"exclude_rules": "HC007"},
    },
    # A recognized --format word is kept as-is: github and junit are members of the
    # format vocabulary, so neither is reset to the human fallback.
    {
        "argv": ["--format", "github", "src/"],
        "equals": {"format": "github", "paths": ["src/"]},
        "contains": {},
    },
    {
        "argv": ["--format", "junit", "src/"],
        "equals": {"format": "junit", "paths": ["src/"]},
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
        try:
            got = parse_args(case["argv"])
        except Exception as exc:  # a mis-wired flag table reaches a missing field
            bad.append(f"parse_args({case['argv']}) raised {exc!r}")
            continue
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
