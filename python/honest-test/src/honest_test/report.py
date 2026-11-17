"""Coverage arithmetic and the run/proof report assemblers (spec sections 9, 11, 8.5).
Every function is pure: it takes measured numbers and data and returns a record.
"""

from honest_test._util import _pick


def coverage_ratio(exercised, total):
    """Compute one coverage dimension's numbers (sections 9.1 through 9.4): exercised and
    total carried back unchanged and their whole-number percentage."""
    pct = _pick(total == 0, lambda: 0, lambda: (exercised * 100) // total)
    return {"total": total, "exercised": exercised, "pct": pct}


def build_coverage_report(vocabularies, chains, honesty, state_machines):
    """Assemble the four coverage dimensions into the CoverageReport (section 9.5),
    stamping the format version."""
    return {
        "version": "1.0",
        "vocabularies": vocabularies,
        "chains": chains,
        "honesty": honesty,
        "state_machines": state_machines,
    }


def build_run_report(chains, links, vocabularies, permutations, failures, adversarial_rejected, coverage, mutation_caught, mutation_total):
    """Assemble the finished RunReport from the measured pieces (section 11)."""
    return {
        "chains": chains,
        "links": links,
        "vocabularies": vocabularies,
        "permutations": permutations,
        "failures": failures,
        "adversarial_rejected": adversarial_rejected,
        "coverage": coverage,
        "mutation_caught": mutation_caught,
        "mutation_total": mutation_total,
    }


def render_report(report):
    """Render the finished RunReport into the section 11 human layout."""
    lines = [
        "honest-test run report",
        f"  chains found:          {report['chains']}",
        f"  links found:           {report['links']}",
        f"  vocabularies found:    {report['vocabularies']}",
        f"  permutations run:      {report['permutations']}",
        f"  failures:              {report['failures']}",
        f"  adversarial rejected:  {report['adversarial_rejected']}",
        f"  mutation caught:       {report['mutation_caught']} / {report['mutation_total']}",
    ]
    return "\n".join(lines) + "\n"


def build_proof_event(function_name, scenario, cases_run, outcome, line_coverage, branch_coverage):
    """Build one hf.proof.checked proof event for a proven function (section 8.5)."""
    return {
        "function_name": function_name,
        "scenario": scenario,
        "cases_run": cases_run,
        "outcome": outcome,
        "line_coverage": line_coverage,
        "branch_coverage": branch_coverage,
    }
