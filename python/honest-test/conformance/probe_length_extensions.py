"""Conformance fragment for the length_extensions scenario (honest-test.feature).

Scenario: length_extensions generates the length-extension neighbor class.
  Then it returns value repeated 10, 100 and 1000 times to shake out quadratic
  behaviour, and value padded to just below, at, and well beyond the uint16
  boundary and toward one megabyte, to expose fixed-buffer assumptions,
  field-length confusion and downstream truncation.
  And it reads no world and returns pure data.

Cases are data; one pure probe feeds them to the real honest_test.length_extensions
and returns a list of failure strings (empty when every case holds). No classes,
no mocks: it calls the real function and asserts the structure the scenario fixes.

Exact padding targets are an implementation detail, so this probe pins the two
families the scenario names: the repetition family (value*10, value*100,
value*1000 present verbatim) and the boundary-padding family (at least one
neighbor at or past the uint16 boundary of 65535, and at least one approaching
one megabyte). Every neighbor must be longer than the input. A stub returning []
fails the first case, so the probe is not vacuous.

This is its own fragment file so the other scenarios' fragments never collide
with it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import length_extensions

_UINT16 = 65535
_MEGABYTE = 1_000_000

_CASES = [
    # A single character: the repetition neighbors are exactly "x" repeated
    # 10, 100 and 1000 times, written out so a stub returning [] cannot pass.
    {
        "value": "x",
        "repetitions": ["x" * 10, "x" * 100, "x" * 1000],
    },
    # A short multi-character value: same two families over a longer unit.
    {
        "value": "ab",
        "repetitions": ["ab" * 10, "ab" * 100, "ab" * 1000],
    },
]


def probe_length_extensions():
    """length_extensions returns the 10/100/1000 repetitions plus padding across the uint16 boundary and toward one megabyte, every neighbor longer than the input."""
    bad = []
    for case in _CASES:
        value = case["value"]
        got = length_extensions(value)

        # (a) the list is non-empty.
        if not got:
            bad.append(f"length_extensions({value!r}) -> {got}, expected a non-empty list")
            continue

        # (b) the repetition family is present verbatim.
        for rep in case["repetitions"]:
            if rep not in got:
                bad.append(
                    f"length_extensions({value!r}) missing repetition neighbor of "
                    f"length {len(rep)} (value repeated {len(rep) // len(value)} times)"
                )

        # (c) the boundary-padding family: one neighbor at/past uint16, one toward 1MB.
        if not any(len(n) >= _UINT16 for n in got):
            bad.append(
                f"length_extensions({value!r}) has no neighbor of length >= {_UINT16} "
                f"(uint16 boundary); longest was {max(len(n) for n in got)}"
            )
        if not any(len(n) >= _MEGABYTE for n in got):
            bad.append(
                f"length_extensions({value!r}) has no neighbor approaching {_MEGABYTE} "
                f"(megabyte region); longest was {max(len(n) for n in got)}"
            )

        # (d) every neighbor is longer than the input.
        for n in got:
            if len(n) <= len(value):
                bad.append(
                    f"length_extensions({value!r}) produced neighbor of length {len(n)}, "
                    f"not longer than the input length {len(value)}"
                )
    return bad


def run():
    bad = probe_length_extensions()
    for line in bad:
        print(line)
    print(f"probe_length_extensions: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)
