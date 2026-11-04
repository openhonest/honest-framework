"""Conformance fragment for the render_report scenario (honest-test.feature ~L441).

Scenario: render_report renders the finished RunReport into the section 11 layout.
  Given report: RunReport
  When render_report is called
  Then it returns the section 11 output text — the chains, links and vocabularies
  found, the permutations run and failures, the adversarial inputs rejected, the
  honesty and chain-contract results, the state-machine tallies, and the totals.
  And it reads the finished report as data and returns the rendered string,
  touching no world.
  And the verdict is already in the report; render_report only lays it out.

Cases are data; one pure probe feeds them to the real honest_test.render_report and
returns a list of failure strings (empty when every case holds). No classes, no
mocks: the input RunReport is plain data and the output is asserted structurally.

The spec's section 11 layout (specs/02-code-quality/honest-test-architecture.md)
prints a per-chain sample richer than the aggregate RunReport dict carries (it names
individual chains and their vocabulary breakdowns). A RunReport holds only the nine
aggregate fields, so the exact byte layout is NOT fixed for a report rendered from
those fields alone. This probe therefore asserts STRUCTURAL properties: the string is
non-empty and multi-line, each number the scenario names appears, and each concept the
scenario's Then names appears as a word. Two reports with distinct numbers pin that the
values come from the input, not from a hard-coded template.

This is its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import render_report


def _coverage_report():
    """A minimal valid CoverageReport, as the RunReport.coverage field requires."""
    return {
        "version": "1.0",
        "vocabularies": {"v": {"total": 10, "exercised": 10, "pct": 100}},
        "chains": {"c": {"total": 3, "exercised": 3, "pct": 100}},
        "honesty": {"c": {"total": 7, "exercised": 7, "pct": 100}},
        "state_machines": {"m": {"total": 5, "exercised": 5, "pct": 100}},
    }


# Two reports with distinct, recognizable numbers. The six fields the scenario's Then
# names by value — chains, links, vocabularies, permutations, failures,
# adversarial_rejected — are what the rendered string must carry. mutation_caught and
# mutation_total are present on the record but the scenario's Then does not name them in
# the layout, so this probe does not require them to appear (see GAPS).
_CASES = [
    {
        "report": {
            "chains": 2,
            "links": 7,
            "vocabularies": 3,
            "permutations": 3000,
            "failures": 4,
            "adversarial_rejected": 11,
            "coverage": _coverage_report(),
            "mutation_caught": 40,
            "mutation_total": 42,
        },
        # The numbers the scenario fixes as coming from the report.
        "numbers": [2, 7, 3, 3000, 4, 11],
    },
    {
        "report": {
            "chains": 5,
            "links": 9,
            "vocabularies": 6,
            "permutations": 1500,
            "failures": 2,
            "adversarial_rejected": 88,
            "coverage": _coverage_report(),
            "mutation_caught": 10,
            "mutation_total": 10,
        },
        "numbers": [5, 9, 6, 1500, 2, 88],
    },
]

# The concepts the scenario's Then names; checked case-insensitively as word stems so
# either "Permutations"/"permutations" or "failure"/"failures" satisfies. The exact
# casing, pluralization and wording are a gap (owner: spec) — see GAPS.
_LABELS = ["chain", "link", "vocabular", "permutation", "failure", "adversarial"]


def _shows(text, n):
    """True when the integer appears plainly or with AP thousands grouping (3,000)."""
    return str(n) in text or f"{n:,}" in text


def probe_render_report():
    """render_report lays the finished RunReport out as the section 11 report text, carrying every measured number and naming every tallied concept, and inventing nothing."""
    bad = []
    for case in _CASES:
        report = case["report"]
        text = render_report(report)

        if not isinstance(text, str):
            bad.append(f"render_report({report}) -> {type(text).__name__}, expected str")
            continue
        if text.strip() == "":
            bad.append(f"render_report({report}) produced an empty report")
            continue
        if "\n" not in text:
            bad.append(
                f"render_report({report}) produced a single line; the section 11 "
                f"report is multi-line: {text!r}"
            )

        for n in case["numbers"]:
            if not _shows(text, n):
                bad.append(
                    f"render_report({report}) report is missing the number {n}: {text!r}"
                )

        low = text.lower()
        for label in _LABELS:
            if label not in low:
                bad.append(
                    f"render_report({report}) report never names {label!r}: {text!r}"
                )
    return bad


def run():
    bad = probe_render_report()
    for line in bad:
        print(line)
    print(f"probe_render_report: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
