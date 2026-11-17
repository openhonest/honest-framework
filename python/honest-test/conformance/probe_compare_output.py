"""Honest probe for honest-test's compare_output (feature Scenario:
compare_output judges one value-oracle output against the known-good value).

compare_output is the pure verdict of the value oracle. It returns honest-type's
ok Result carrying the output when the output equals the expected value, and
honest-type's err Result carrying an expected-vs-got fault when they differ. The
output is compared whole, so a function that returns a Result has its Result as
its expected value (.hd compare_output; architecture section 8.6).

The probe calls the real function with concrete (output, expected) pairs and
recognizes the verdict by shape: an ok Result carries an "ok" key holding the
output, and an err Result carries an "err" key holding a honest-type fault (a
dict with a "code"). The whole-value comparison is exercised with dict outputs
that are themselves Result-shaped.
"""

from honest_test import compare_output


def _is_ok(result):
    return isinstance(result, dict) and "ok" in result


def _is_err(result):
    return isinstance(result, dict) and "err" in result


def probe_compare_output():
    """compare_output returns ok carrying the output when it equals expected, and
    err carrying a fault when it differs, comparing the value whole."""
    bad = []

    equal = compare_output(42, 42)
    if not _is_ok(equal):
        bad.append(f"an output equal to expected should return an ok Result, got {equal!r}")
    elif equal.get("ok") != 42:
        bad.append(f"the ok Result should carry the output 42, got {equal.get('ok')!r}")

    different = compare_output(42, 7)
    if not _is_err(different):
        bad.append(f"an output differing from expected should return an err Result, got {different!r}")
    else:
        fault = different.get("err")
        if not (isinstance(fault, dict) and "code" in fault):
            bad.append(f"the err Result should carry a fault with a code, got {fault!r}")

    whole_equal = compare_output({"ok": "x"}, {"ok": "x"})
    if not _is_ok(whole_equal):
        bad.append(f"a Result-shaped output equal to a Result-shaped expected should return ok, got {whole_equal!r}")

    whole_different = compare_output({"ok": "x"}, {"ok": "y"})
    if not _is_err(whole_different):
        bad.append(f"a Result-shaped output differing from expected should return err, got {whole_different!r}")

    return bad


def run():
    messages = probe_compare_output()
    for message in messages:
        print(f"FAIL HT-probe [compare_output]: {message}")
    passed = 0 if messages else 1
    print(f"compare_output: {passed} passed, {len(messages)} failed")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
