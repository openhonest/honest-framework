"""Coverage records and the run report (spec section 9, section 11).

coverage_ratio is the one computation shared by all four dimensions; build_coverage_report and
build_run_report assemble the records; render_report lays the finished report out as text. All
pure: they read their arguments as data and touch no world.
"""

_COVERAGE_VERSION = "1.0"


def coverage_ratio(exercised, total):
    """Compute one coverage dimension's numbers (spec sections 9.1-9.4): exercised, total, and
    their floored whole-number percentage, which never over-reports. total of zero has nothing to
    cover and reports 100 (vacuously complete). Reads no world, returns pure data."""
    pct = 100 if total == 0 else (exercised * 100) // total
    return {"total": total, "exercised": exercised, "pct": pct}


def build_coverage_report(vocabularies, chains, honesty, state_machines):
    """Assemble the four coverage dimensions into the CoverageReport (spec section 9.5), stamping
    the format version. Reads no world, returns pure data."""
    return {
        "version": _COVERAGE_VERSION,
        "vocabularies": vocabularies,
        "chains": chains,
        "honesty": honesty,
        "state_machines": state_machines,
    }


def build_run_report(chains, links, vocabularies, permutations, failures, adversarial_rejected,
                     coverage, mutation_caught, mutation_total):
    """Assemble the finished RunReport from the measured pieces (spec section 11). Reads its
    arguments as data and touches no world."""
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
    """Render the finished RunReport into the section 11 human layout (spec section 11): the
    chains, links and vocabularies found, the permutations and failures, the adversarial inputs
    rejected, and the mutation tally. Reads the report as data and returns the rendered string."""
    lines = [
        "honest-test report",
        f"chains: {report['chains']}",
        f"links: {report['links']}",
        f"vocabularies: {report['vocabularies']}",
        f"permutations: {report['permutations']}",
        f"failures: {report['failures']}",
        f"adversarial rejected: {report['adversarial_rejected']}",
        f"honesty and chain-contract results: {report['failures']} failure(s)",
        f"state machines: {report['vocabularies']} declared",
        f"mutation caught: {report['mutation_caught']}/{report['mutation_total']}",
    ]
    return "\n".join(lines)
