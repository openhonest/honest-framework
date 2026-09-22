#!/usr/bin/env python3
"""rules-check.py — the rule catalogue and the linter must agree.

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
QUOTED_ID = re.compile(r"['\"](HC-(?:[A-Z]{1,3}\d{2,3}|SYN)|HC\d{3})['\"]")
ROOT = pathlib.Path(__file__).resolve().parent.parent


def emitted_ids(sources: list[str]) -> set[str]:
    """Pure: every rule id the linter's own source EMITS, read as a quoted string rather than as
    text anywhere in the file.

    Matching the bare id counted a comment as an implementation. HC-REF005 was named in two
    comments, both saying a missing declaration is its finding, and in no code at all; the
    catalogue recorded it as emitted and this check agreed, so a rule that has never existed
    passed as implemented from August to September. A rule reaches a reader by being constructed,
    and construction means the id is a string in the source.

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


def main() -> int:
    catalogue = json.loads((ROOT / "specs/rules.json").read_text(encoding="utf-8"))["rules"]
    sources = [p.read_text(encoding="utf-8")
               for p in sorted((ROOT / "python/honest-check/src/honest_check").rglob("*.py"))]
    emitted = emitted_ids(sources)
    problems = disagreements(catalogue, emitted)
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
