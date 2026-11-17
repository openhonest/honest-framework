"""honest-test conformance: length_extensions — the length-extension neighbor class.

The spec fixes this list exactly (§3.5, class 4): the value repeated 10, 100 and 1000
times, and the value padded with 'A' to 65535, 65536 and 1048575 characters — the near- and
at-uint16 boundary and toward one megabyte. This probe carries that formula as its oracle
and asserts the real length_extensions produces exactly those six neighbors.

No classes, no mocks. It calls the real honest_test.length_extensions and compares sets.
"""

from honest_test import length_extensions


def _reference(value):
    """The §3.5 class-4 formula transcribed from the spec, the known-good oracle."""
    return [
        value * 10,
        value * 100,
        value * 1000,
        value + ("A" * 65535),
        value + ("A" * 65536),
        value + ("A" * 1048575),
    ]


def probe_length_extensions():
    bad = []
    value = "ab"
    got = length_extensions(value)
    if not isinstance(got, list):
        return [f"length_extensions({value!r}) -> {type(got).__name__}, expected a list"]
    expected = set(_reference(value))
    got_set = set(got)
    if got_set != expected:
        missing = {len(s) for s in expected - got_set}
        extra = {len(s) for s in got_set - expected}
        if missing:
            bad.append(f"length_extensions({value!r}) is missing neighbors of lengths {sorted(missing)}")
        if extra:
            bad.append(f"length_extensions({value!r}) produced unexpected neighbors of lengths {sorted(extra)}")
    return bad


def run():
    messages = probe_length_extensions()
    if messages:
        print(f"FAIL HTEST-probe [length_extensions]: {messages}")
    print(f"length_extensions: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 1 if messages else 0


if __name__ == "__main__":
    raise SystemExit(run())
