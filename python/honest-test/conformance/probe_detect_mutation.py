"""Conformance fragment for the detect_mutation scenario (honest-test.feature).

Scenario: detect_mutation runs a link on a copied manifest and reports
  manifest_mutated when the input changed.
  Then it deep-copies the manifest, runs the link, and returns a manifest_mutated
  failure Finding when the manifest after the run differs from the copy, because a
  pure function must not modify its input.
  And it returns the failure as a one-element list, or the empty list when the
  input was untouched.

Cases are data; one pure probe feeds them to the real function and returns a list
of failure strings (empty when every case holds). No classes, no mocks: the link
is injected as a real plain function, and the probe calls the real
honest_test.detect_mutation.

The link is a Callable injected as a real test input. pure_link builds a new dict
and leaves its input untouched; mutating_link assigns into the input dict in place.
A Manifest is a plain dict.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import detect_mutation


def pure_link(manifest):
    """A pure link: builds a new dict, leaves the input manifest untouched."""
    return {**manifest, "out": 1}


def mutating_link(manifest):
    """A dishonest link: mutates the input manifest dict in place."""
    manifest["injected"] = True
    return manifest


_CASES = [
    # A pure link touches nothing, so detect_mutation returns the empty list.
    # This is the explicit absence case (input untouched -> []).
    {
        "link": pure_link,
        "test_manifest": {"color": "red", "size": "small"},
        "expect_count": 0,
    },
    # A link that assigns into its input dict mutates the manifest, so
    # detect_mutation returns exactly one manifest_mutated failure.
    {
        "link": mutating_link,
        "test_manifest": {"color": "red", "size": "small"},
        "expect_count": 1,
    },
]


def probe_detect_mutation():
    """detect_mutation returns one manifest_mutated failure when a link changes its input manifest, and the empty list when the input is untouched."""
    bad = []
    for case in _CASES:
        # detect_mutation must copy before running; pass a fresh manifest anyway
        # so one case cannot contaminate the next.
        manifest = dict(case["test_manifest"])
        got = detect_mutation(case["link"], manifest)
        if len(got) != case["expect_count"]:
            bad.append(
                f"detect_mutation({case['link'].__name__}, {case['test_manifest']}) "
                f"-> {len(got)} finding(s), expected {case['expect_count']}"
            )
            continue
        if case["expect_count"] == 1:
            finding = got[0]
            code = finding["code"] if isinstance(finding, dict) else finding.code
            kind = finding["kind"] if isinstance(finding, dict) else finding.kind
            if code != "manifest_mutated":
                bad.append(
                    f"detect_mutation({case['link'].__name__}, {case['test_manifest']}) "
                    f"-> code {code!r}, expected 'manifest_mutated'"
                )
            if kind != "failure":
                bad.append(
                    f"detect_mutation({case['link'].__name__}, {case['test_manifest']}) "
                    f"-> kind {kind!r}, expected 'failure'"
                )
    return bad


def run():
    bad = probe_detect_mutation()
    for line in bad:
        print(line)
    print(f"probe_detect_mutation: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
