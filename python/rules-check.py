#!/usr/bin/env python3
"""rules-check.py — the rule catalogue and the checker must agree.

`specs/rules.json` is the single declaration of every honest-check rule: its id, severity, firing
time, what it makes impossible, and which module enforces it. The spec tables are projections of
that record, and honest-check's source is its implementation. This gate asserts the two agree, in
both directions:

  - a rule id emitted by honest-check that the catalogue does not declare  -> undeclared rule
  - a rule the catalogue says honest-check emits, that it does not         -> phantom rule

The second direction is the one that misleads. A reader takes the catalogue as the list of what is
enforced, so a rule documented but never written reads as protection that is not there. Three such
rules sat in the tables for months (HC-P008, HC-P009, HC-P012) because nothing compared the list to
the code; they are declared here as honest-test's, with `emitted_by_honest_check: false`, which is a
statement of fact rather than an omission.

Not linted (the boundary): main() reads the files and exits with a status. Both decisions above
it are pure and take their data as arguments.
"""

import json
import pathlib
import re
import sys

# The id families the catalogue actually uses. Deliberately exact: a loose pattern picks up
# docstring text ("HC-P* rules", the "HC-XXXX" placeholder in the suppression example) and
# reports it as an undeclared rule.
ID = re.compile(r"HC-(?:[A-Z]{1,3}\d{2,3}|SYN)\b|HC\d{3}\b")
# A rule is emitted where its id appears as a quoted literal in a rule-logic file. Two earlier
# predicates were each wrong, in opposite directions. Matching the bare id counted a comment as
# an implementation. Anchoring to diagnostic( to exclude the adoption table missed the mark two
# ways at once: the id is diagnostic's SECOND argument, after ctx, so diagnostic\(\s*['"] matched
# nothing and branded all sixty rules phantom; and most declared-tier rules build their finding
# through another constructor, never diagnostic(, so even the right argument position would miss
# them. The real line is the file, not the call shape: report.py advertises the catalogue (the
# membership frozensets and the adoption table) without emitting anything, and every other source
# file names a rule id only where it constructs that rule. So scan the quoted ids everywhere but
# report.py.
QUOTED_ID = re.compile(r"['\"](HC-(?:[A-Z]{1,3}\d{2,3}|SYN)|HC\d{3})['\"]")
ADVERTISEMENT = "report.py"
ROOT = pathlib.Path(__file__).resolve().parent.parent


def emitted_ids(sources: list[str]) -> set[str]:
    """Pure: every rule id emitted, read as a quoted literal in the rule sources it is given.

    The caller passes every source file but report.py. report.py advertises the catalogue — the
    membership frozensets and the adoption table — without constructing a single finding, so its
    quoted ids once reported the whole catalogue as implemented. Every remaining file names a rule
    id only where it builds that rule's finding, so a quoted id there is an emission, whatever
    constructor carries it. Matching the bare id instead counted a comment as an implementation:
    HC-REF005 was named in two comments saying a missing declaration is its finding, and in no code
    at all, and from August to September a rule that had never existed passed as implemented.

    Takes the text, not the path, so the extraction is exercised without a filesystem."""
    return {m.group(1) for m in QUOTED_ID.finditer(" ".join(sources))}


def disagreements(catalogue: list[dict], emitted: set[str]) -> list[str]:
    """Pure: the two directions of drift, as reportable lines."""
    declared_emitting = {r["id"] for r in catalogue if r["emitted_by_honest_check"]}
    declared_all = {r["id"] for r in catalogue}
    out = []
    for rid in sorted(emitted - declared_all):
        out.append(f"  UNDECLARED  {rid} is emitted by honest-check but is in no catalogue record.")
    for rid in sorted(declared_emitting - emitted):
        out.append(f"  PHANTOM     {rid} is declared as emitted by honest-check, which emits nothing for it.")
    for rid in sorted((emitted & declared_all) - declared_emitting):
        out.append(f"  MISDECLARED {rid} is declared not-emitted, but honest-check emits it.")
    return out


def unplaced_rules(catalogue: list, placed: set) -> list[str]:
    """Rules honest-check emits that the adoption level table does not place.

    The level table is a second list of the same rules, so it drifts from the catalogue the way any
    copy does. A rule missing from it used to be downgraded to info, which is a rule that runs,
    reports real findings and blocks nothing. HC-P018 sat there from the day it was written and
    HC-REF005 joined it on its first run, so the drift is checked rather than trusted.

    placed is the full Declared-level membership, which main reads from report.enforced_rules_of
    rather than scraping report.py's text. The earlier version split the source on symbol names
    (_LEVEL_RULES, ALWAYS_ENFORCED) a later report.py no longer used, so it matched nothing and
    placed came back empty.
    """
    return [f"  {r['id']} is emitted and the adoption level table does not place it, so it reports as info and blocks nothing."
            for r in catalogue
            if r["emitted_by_honest_check"] and r["id"] not in placed]


def main() -> int:
    from honest_check.report import enforced_rules_of, _LEVEL_ORDER
    catalogue = json.loads((ROOT / "specs/rules.json").read_text(encoding="utf-8"))["rules"]
    sources = [p.read_text(encoding="utf-8")
               for p in sorted((ROOT / "python/honest-check/src/honest_check").rglob("*.py"))
               if p.name != ADVERTISEMENT]
    emitted = emitted_ids(sources)
    placed = set(enforced_rules_of(_LEVEL_ORDER[-1]))
    problems = disagreements(catalogue, emitted)
    problems += unplaced_rules(catalogue, placed)
    if problems:
        print("rules-check: the catalogue and honest-check disagree.", file=sys.stderr)
        print("\n".join(problems), file=sys.stderr)
        print("  Fix the code, or amend specs/rules.json — whichever states the truth.", file=sys.stderr)
        return 1
    # Two different facts, kept apart. A rule another module owns is covered somewhere. A rule
    # honest-check owns and has not written is covered nowhere, and calling both "enforced
    # elsewhere" told a reader the second was handled.
    elsewhere = [r["id"] for r in catalogue
                 if not r["emitted_by_honest_check"] and r["enforced_by"] != "honest-check"]
    unwritten = [r["id"] for r in catalogue
                 if not r["emitted_by_honest_check"] and r["enforced_by"] == "honest-check"]
    print(f"rules-check: {len(catalogue)} rules declared, {len(emitted)} emitted by honest-check, "
          f"{len(elsewhere)} owned by another module ({', '.join(elsewhere)}).")
    if unwritten:
        print(f"  {len(unwritten)} declared by honest-check and NOT written: {', '.join(unwritten)}. "
              f"Nothing enforces these.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
