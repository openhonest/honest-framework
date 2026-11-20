"""The schema loader: the host's declared Pydantic models read into a Declared.

A reduced loader. A host declares a model as a Pydantic class carrying `__tablename__` and a view as one
carrying `__viewname__` and `__declaration__`. This walks the Pydantic register and reads the basic
column types; a type it has no word for or a model it cannot read is a column left to the empty answer
rather than a crash, because schema_read_declared wraps this and answers an empty Declared on any failure.
A host that declared nothing — the usual case when honest-persist is handed a database to drive without
managing its schema — produces an empty Declared.
"""

from honest_persist._util import _pick, _read_or
from honest_persist.types import DECLARED_TYPES


def _basic_type(annotation):
    """The honest-persist word for a basic Python annotation, or text when unknown."""
    return _read_or(_BY_PY_TYPE, annotation, lambda: "text")


_BY_PY_TYPE = {int: "integer", str: "text", float: "float", bool: "boolean", bytes: "bytes"}


def _a_column(name, annotation):
    declared = _basic_type(annotation)
    return {"name": name, "declared_type": _pick(declared in DECLARED_TYPES, lambda: declared, lambda: "text"),
            "renamed_from": None, "references": None}


def _declared_on(cls, attribute, nobody_said):
    return getattr(cls, attribute, nobody_said)


def _a_model(cls):
    fields = getattr(cls, "model_fields", {})
    return {
        "name": cls.__name__, "table": cls.__tablename__,
        "columns": [_a_column(name, getattr(field, "annotation", str)) for name, field in fields.items()],
        "dropping": _declared_on(cls, "__dropping__", []),
        "indexes": _declared_on(cls, "__indexes__", []),
        "constraints": _declared_on(cls, "__constraints__", []),
    }


def _a_view(cls):
    return {"name": cls.__viewname__, "declaration": cls.__declaration__,
            "freshness": _declared_on(cls, "__freshness__", None),
            "cadence": _declared_on(cls, "__cadence__", None),
            "attempts_allowed": _declared_on(cls, "__attempts_allowed__", None)}


def _descendants(cls):
    children = cls.__subclasses__()
    return [found for child in children for found in [child, *_descendants(child)]]


def load_declared():
    """Every Pydantic model the host declared, as a Declared. Raises ImportError when Pydantic is not
    installed, which schema_read_declared reads as the host having declared nothing."""
    from pydantic import BaseModel

    classes = list(dict.fromkeys(_descendants(BaseModel)))
    models = [_a_model(cls) for cls in filter(lambda c: hasattr(c, "__tablename__"), classes)]
    views = [_a_view(cls) for cls in filter(lambda c: hasattr(c, "__viewname__"), classes)]
    dropping_tables = list(dict.fromkeys(
        name for cls in filter(lambda c: hasattr(c, "__dropping_tables__"), classes)
        for name in cls.__dropping_tables__))
    dropping_views = list(dict.fromkeys(
        name for cls in filter(lambda c: hasattr(c, "__dropping_views__"), classes)
        for name in cls.__dropping_views__))
    return {"models": models, "views": views, "dropping_tables": dropping_tables,
            "dropping_views": dropping_views}
