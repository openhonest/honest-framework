"""honest-observe conformance runner (core unit).

honest-observe's portable contract (suite.json) is value_cases over its data-pure functions whose
whole output the feature scenario fixes -- extract_auth, extract_meta, build_event (the ok arm),
matches, apply_projection -- checked centrally by value-check.py (honest-test section 8.6). apply_projection
takes a fold Callable, so the value map exposes a fixture fold (count_fold) a value case can $ref.

The I/O emit path (new_event_id, event_timestamp, next_sequence, append_event, run_emit, emit) and the
pure functions whose whole output the one-line scenario does not fix (the Fault arms, the projection
and metric handles, the hlc rules, the identity fold and resolve, request_canonical, event_log_schema)
are carried by laws_ho.py, which drives emit against a REAL in-memory sqlite event log.

  uv run --package honest-observe python honest-observe/conformance/run_conformance.py
"""

import honest_observe as _ho


def _count_fold(state, event):
    """A fixture fold a value case $refs to reach apply_projection, which takes a fold Callable. It
    counts every event folded in -- state + 1 -- so the value case asserts a plain, non-circular
    projection count. Fixture, not gated library code."""
    return state + 1


# The value-oracle function map proof_run and value-check.py read: the module's public callables, the
# internal pure functions whose whole output a value case fixes (reached by invokes, so importable but
# not in __all__ -- extract_auth, extract_meta, build_event, matches -- exposed by name exactly as
# honest-auth exposes auth_fault and its outcome checkers), plus the fixture fold. A value case whose
# function is absent from this map is silently skipped by value-check, the silent-miss P16 names, so the
# map is closed over every function a suite.json case names rather than left to __all__ alone.
_INTERNAL_VALUE_FUNCTIONS = ["observe_fault", "extract_auth", "extract_meta", "build_event", "matches"]
_VALUE_FUNCTIONS = {
    **{name: getattr(_ho, name) for name in getattr(_ho, "__all__", []) if callable(getattr(_ho, name, None))},
    **{name: getattr(_ho, name) for name in _INTERNAL_VALUE_FUNCTIONS},
    "count_fold": _count_fold,
}


def run(_suite_path=None):
    """No data cases to run here -- the portable cases are all value cases (checked by value-check.py);
    the behavioural checks a data file cannot express are the laws in laws_ho.py."""
    return 0


if __name__ == "__main__":
    import laws_ho

    raise SystemExit(run() or laws_ho.run())
