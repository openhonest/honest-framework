# scenario: log_write sends a warning event at warning severity
# inherits: hd=python/honest-persist/honest-persist.hd::log_write -> feature=specs/features/honest-persist.feature::log_write sends a warning event at warning severity

import logging
from io import StringIO

from honest_persist import log_write


def probe_log_write_warning_severity():
    output = StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger = logging.getLogger("honest_persist")
    old_level = logger.level
    logger.addHandler(handler)
    failures = []
    failures = []
    try:
        logger.setLevel(logging.DEBUG)
        for level in ("debug", "info", "warning", "error", "critical"):
            output.seek(0)
            output.truncate(0)
            try:
                result = log_write({"level": level, "db": "example"})
            except Exception as error:
                failures.append(f"{level} event raised {type(error).__name__}: {error}")
                continue
            rows = output.getvalue().splitlines()
            if result is not None or len(rows) != 1:
                failures.append(f"{level} event returned {result!r} and emitted {rows!r}, expected NOTHING and one line")
                continue
            severity, *facts = rows[0].split()
            expected_severity = level.upper()
            if severity != expected_severity or {f"level={level}", "db=example"} - set(facts):
                failures.append(f"{level} event emitted {rows[0]!r}, expected one {expected_severity} line carrying both facts")
    finally:
        logger.setLevel(old_level)
        logger.removeHandler(handler)
        handler.close()

    return failures
