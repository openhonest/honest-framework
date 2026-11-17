"""honest-test conformance: verify_under_monitor runs a link under the injected monitor.

Spec sections 4.4 and 4.5, feature "verify_under_monitor runs a link under the injected
monitor", .hd verify_under_monitor. One body serves both checks: it runs the link inside
the injected monitor and returns a warning when the monitor recorded a watched call and
the link is not a declared boundary — io_detected for kind io, nondeterminism_detected
for kind nondeterminism. The warning reports and does not block; the empty list means the
monitor recorded nothing.

No classes, no mocks. The monitor is injected as a real callable: monitor(link, manifest)
runs the link and returns the record of detected calls as a collection. A quiet monitor
returns an empty record (no watched call); a noisy monitor returns a non-empty record. The
link is a plain, non-boundary function. A Finding carries a "code" and a "kind".
"""

from honest_type import link

from honest_test import verify_under_monitor


def _codes(findings):
    return [f.get("code") for f in findings if isinstance(f, dict)]


def _link(manifest):
    return {"ok": manifest}


@link(boundary=True)
def _boundary_link(manifest):
    """A declared boundary: it is allowed to perform I/O, so a watched call is not a warning."""
    return {"ok": manifest}


def _quiet_monitor(link, manifest):
    """Runs the link and reports no watched call."""
    link(manifest)
    return []


def _noisy_monitor(link, manifest):
    """Runs the link and reports a watched call was detected."""
    link(manifest)
    return ["builtins.open"]


def probe_verify_under_monitor():
    bad = []
    manifest = {"slot": "value"}

    clean_io = verify_under_monitor(_link, manifest, _quiet_monitor, "io")
    if clean_io != []:
        bad.append(f"an empty io record should yield no warning, got {clean_io!r}")

    warn_io = verify_under_monitor(_link, manifest, _noisy_monitor, "io")
    if _codes(warn_io) != ["io_detected"]:
        bad.append(
            f"a non-empty io record on a non-boundary link should yield one io_detected "
            f"warning, got {warn_io!r}"
        )
    elif warn_io[0].get("kind") != "warning":
        bad.append(f"the io_detected finding must be graded a warning, got kind {warn_io[0].get('kind')!r}")

    boundary = verify_under_monitor(_boundary_link, manifest, _noisy_monitor, "io")
    if boundary != []:
        bad.append(
            f"a declared boundary link is allowed I/O, so a watched call must not warn, got {boundary!r}"
        )

    clean_nd = verify_under_monitor(_link, manifest, _quiet_monitor, "nondeterminism")
    if clean_nd != []:
        bad.append(f"an empty nondeterminism record should yield no warning, got {clean_nd!r}")

    warn_nd = verify_under_monitor(_link, manifest, _noisy_monitor, "nondeterminism")
    if _codes(warn_nd) != ["nondeterminism_detected"]:
        bad.append(
            f"a non-empty nondeterminism record on a non-boundary link should yield one "
            f"nondeterminism_detected warning, got {warn_nd!r}"
        )
    elif warn_nd[0].get("kind") != "warning":
        bad.append(
            f"the nondeterminism_detected finding must be graded a warning, got kind "
            f"{warn_nd[0].get('kind')!r}"
        )

    return bad


def run():
    messages = probe_verify_under_monitor()
    for message in messages:
        print(f"FAIL HT-probe [verify_under_monitor]: {message}")
    print(f"verify_under_monitor: {'passed' if not messages else f'{len(messages)} failed'}")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())
