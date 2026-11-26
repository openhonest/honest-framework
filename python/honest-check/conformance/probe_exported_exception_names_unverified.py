# scenario: exported_exception_names excludes unresolved and non-exception bindings
# inherits: hd=python/honest-check/honest-check.hd::exported_exception_names -> feature=specs/features/honest-check.feature::exported_exception_names excludes unresolved and non-exception bindings
_CASES = [(b'from .absent import MissingError\n__all__ = ["MissingError", "ReboundError", "Ord'
  b'inary", "run"]\n\nclass ReboundError(Exception):\n    pass\n\nReboundError = fact'
  b'ory()\n\nclass Ordinary:\n    pass\n\ndef run():\n    return 1\n',
  {},
  set()),
 (b'from .errors import LocalError as PublicError\n__all__ = ["PublicError"]\n',
  {'src/example/errors.py': b'class LocalError(Exception): pass\n',
   'src/example/errors/__init__.py': b'class LocalError(Exception): pass\n'},
  set()),
 (b'__all__ = ["ShadowedConstructorError", "ShadowedBaseError"]\ntype = factory\nShado'
  b'wedConstructorError = type("ShadowedConstructorError", (Exception,), {})\nExcepti'
  b'on = factory()\n\nclass ShadowedBaseError(Exception):\n    pass\n',
  {},
  set()),
 (b'from .forward import RealError as ForwardedError\n__all__ = ["ForwardedError", "I'
  b'nheritedError", "AssignedError"]\n\nclass RealError(Exception):\n    pass\n\nclas'
  b's InheritedError(RealError):\n    pass\n\nAssignedError = RealError\n',
  {'src/example/errors.py': b'class RealError(Exception): pass\n',
   'src/example/forward.py': b'from .errors import RealError\n'},
  set())]

_REBOUND_EXPORTS = b"""
from helpers import dynamic_decorator

class ImportErrorAlias(Exception):
    pass

import ordinary as ImportErrorAlias

class AugmentedError(Exception):
    pass

AugmentedError += 1

class DecoratedCallableError(Exception):
    pass

@dynamic_decorator
def DecoratedCallableError():
    return 1

@dynamic_decorator
class DecoratedClassError(Exception):
    pass

__all__ = ["ImportErrorAlias", "AugmentedError", "DecoratedCallableError", "DecoratedClassError"]
"""
_CASES.append((_REBOUND_EXPORTS, {}, set()))
_CASES.append((
    b'__all__ = ["AugmentedError"]\n'
    b'from .base import *\n'
    b'AugmentedError += type("AugmentedError", (Exception,), {})\n',
    {"src/example/base.py": b"class Collector:\n    def __iadd__(self, value): return self\nAugmentedError = Collector()\n"},
    set(),
))

_CASES.extend((
    (
        b'class ReplacedError(Exception): pass\ndef ReplacedError(): return 1\n__all__ = ["ReplacedError"]\n',
        {},
        set(),
    ),
    (
        b'from ..errors import LocalError as PublicError\n__all__ = ["PublicError"]\n',
        {"src/example/errors.py": b"class LocalError(Exception): pass\n"},
        set(),
    ),
))


def probe_exported_exception_names_unverified():
    """Compare the verified public export set for each supplied package."""
    try:
        from honest_check.crossing import exported_exception_names
    except ImportError as exc:
        return [f"cannot import exported_exception_names: {exc}"]

    failures = []
    for export_source, other_sources, expected in _CASES:
        files = {"src/example/__init__.py": export_source, **other_sources}
        sources = [{"path": path, "text": source} for path, source in files.items()]
        actual = exported_exception_names(sources, export_source)
        if actual != expected:
            failures.append(
                f"exported_exception_names returned {actual!r}, expected {expected!r} "
                f"for {export_source!r}"
            )
    return failures
