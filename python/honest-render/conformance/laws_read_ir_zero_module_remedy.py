# scenario: read_ir asks the caller to supply one module when none are declared
# inherits: hd=python/honest-render/honest-render.hd::read_ir -> feature=specs/features/honest-render.feature::read_ir asks the caller to supply one module when none are declared
import re

from honest_type import is_fault

from honest_render import read_ir

_SOURCE = '# no modules\n'
_COUNT = '0'
_PROBLEM = '\\b(?:no|zero|0) modules?\\b|\\bdoes not declare a module\\b'
_REMEDY = '\\b(?:supply|provide|include|add|declare) (?:exactly )?(?:one|a single|a) module\\b'


def probe_read_ir_zero_module_remedy():
    fault = read_ir(_SOURCE)
    if not is_fault(fault) or fault.get("is_err") is not True or "ok" in fault or "err" in fault:
        return [f"Expected a bare Fault with is_err true, got {fault!r}"]
    failures = []
    if (fault.get("code"), fault.get("category")) != ("not_single_module", "client"):
        failures.append(f"Expected not_single_module/client, got {fault!r}")
    detail = fault.get("detail")
    if not isinstance(detail, dict) or detail.get("module_count") != _COUNT:
        failures.append(f"Expected detail.module_count={_COUNT!r}, got {detail!r}")
    message = fault.get("message")
    if not isinstance(message, str) or not all(re.search(pattern, message, re.I) for pattern in (_PROBLEM, _REMEDY)):
        failures.append(f"Expected the message to explain the missing module and ask for one module, got {message!r}")
    return failures
