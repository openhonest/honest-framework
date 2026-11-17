"""honest-test conformance: render_report — the human report layout.

render_report(report) turns a RunReport into the §11 human text: the chains, links
and vocabularies found, the permutations run and failures, and the adversarial
inputs rejected. This probe asserts the rendered string shows each of those counts.
The counts here are distinct small numbers that share no digits, so each presence
check is a real one rather than an accidental digit overlap.

No classes, no mocks. It calls the real honest_test.render_report.
"""

from honest_test import render_report


def probe_render_report():
    bad = []
    coverage = {
        "version": "1.0",
        "vocabularies": {},
        "chains": {},
        "honesty": {},
        "state_machines": {},
    }
    report = {
        "chains": 4,
        "links": 12,
        "vocabularies": 6,
        "permutations": 88,
        "failures": 5,
        "adversarial_rejected": 73,
        "coverage": coverage,
        "mutation_caught": 2,
        "mutation_total": 2,
    }

    text = render_report(report)
    if not isinstance(text, str):
        return [f"render_report returned {text!r}, expected a string"]
    if not text.strip():
        bad.append("render_report returned an empty string")
    for name in ("chains", "links", "vocabularies", "permutations", "failures", "adversarial_rejected"):
        if str(report[name]) not in text:
            bad.append(f"the rendered report does not show the {name} count {report[name]}")
    return bad


def run():
    messages = probe_render_report()
    if messages:
        print(f"FAIL HTEST-probe [render_report]: {messages}")
    print(f"render_report: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 1 if messages else 0


if __name__ == "__main__":
    raise SystemExit(run())
