# scenario: log_write emits an event with an unrecognized scalar level
# inherits: hd=python/honest-persist/honest-persist.hd::log_write -> feature=specs/features/honest-persist.feature::log_write emits an event with an unrecognized scalar level

import logging
from io import StringIO

from honest_persist import log_write


def probe_log_write_unknown_level():
    output = StringIO()
    handler = logging.StreamHandler(output)
    logger = logging.getLogger("honest_persist")
    old_level = logger.level
    logger.addHandler(handler)
    try:
        logger.setLevel(logging.DEBUG)
        result = log_write({"level": 17, "db": "example"})
    except Exception as error:
        return [f"unrecognized numeric level raised {type(error).__name__}: {error}"]
    finally:
        logger.setLevel(old_level)
        logger.removeHandler(handler)
        handler.close()

    rows = output.getvalue().splitlines()
    if result is not None or len(rows) != 1 or {"level=17", "db=example"} - set(rows[0].split()):
        return [f"unrecognized numeric level returned {result!r} and emitted {rows!r}, expected NOTHING and one line carrying both facts"]
    return []
