"""Coverage data format (section 9.5): the coverage.json honest-check reads for HC-P009 and cross-tool checks.

honest-test measures four coverage dimensions (sections 9.1-9.4) — vocabulary members, chain fault exit
points, link honesty, and state-machine transitions — and writes them as one coverage.json. Building each
record and assembling the document are pure (the timestamp is generated at the boundary and passed in,
exactly as the event envelope's is). Writing the file is the one I/O step, reached through an injected
writer, so honest-test stays testable without touching the filesystem. honest-check reads the file back as
the structure these builders produce — the file is the cross-tool contract between the two.
"""

import json

_VERSION = "1.0"


def _pct(part, whole):
    """A coverage percentage: `part` of `whole` as a whole number, or 100 when there is nothing to cover."""
    return round(part / whole * 100) if whole else 100


def vocabulary_coverage(total, exercised):
    """Vocabulary coverage for one vocabulary (section 9.1): the Set members exercised out of the total,
    with the percentage. Pure."""
    return {"total": total, "exercised": exercised, "pct": _pct(exercised, total)}


def chain_coverage(fault_paths, exercised):
    """Chain coverage for one chain (section 9.2): the fault exit points exercised out of the total, with
    the percentage. Pure."""
    return {"fault_paths": fault_paths, "exercised": exercised, "pct": _pct(exercised, fault_paths)}


def honesty_coverage(total, honest, boundary):
    """Honesty coverage for one chain (section 9.3): how many links passed the honesty tests out of the
    total, with the boundary links (exempt, reported separately) noted. Pure."""
    return {"total": total, "honest": honest, "boundary": boundary, "pct": _pct(honest, total)}


def state_machine_coverage(transitions, exercised):
    """State-machine coverage for one machine (section 9.4): the declared transitions exercised, with the
    percentage. Pure."""
    return {"transitions": transitions, "exercised": exercised, "pct": _pct(exercised, transitions)}


def build_coverage(vocabularies, chains, honesty, state_machines, timestamp):
    """Assemble the coverage document (section 9.5): the version, the run timestamp, and the four coverage
    maps keyed by name. Pure — the timestamp is generated at the boundary and passed in."""
    return {
        "version": _VERSION,
        "timestamp": timestamp,
        "vocabularies": vocabularies,
        "chains": chains,
        "honesty": honesty,
        "state_machines": state_machines,
    }


def write_coverage(coverage, path, write):
    """Write the coverage document to coverage.json (section 9.5). The serialization is pure; the write is
    the one I/O step, reached through the injected `write(path, text)`. honest-check reads the file back as
    the structure build_coverage produced."""
    write(path, json.dumps(coverage, indent=2))
