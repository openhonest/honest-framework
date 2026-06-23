"""The Pydantic schema loader (section 2): read @table-decorated BaseModel subclasses to a Schema.

A schema is plain data; this is the idiomatic Python way to produce it, reading the field types,
Literal annotations, and Field metadata of Pydantic models. It is a pure function — no I/O, no
database — and an optional adapter: a hand-written Schema dict is equally valid (section 2.2), so the
pure core never imports Pydantic and this module is reached only through honest-persist[pydantic].

Reading the host language's type system is inherently introspective — typing.get_type_hints,
get_origin, and type() to map Python types to abstract SQL types — so HC-P005 is disabled for this
file alone. This is the one boundary where the framework inspects Python types rather than its own
data; everywhere else the schema is a dict and no type introspection is needed.
"""
# honest: disable HC-P005

from typing import Literal, get_args, get_origin, get_type_hints

from pydantic_core import PydanticUndefined

# Python type (or its name, for forward-referenced imports) to abstract SQL type (section 2.3). The
# applier resolves the abstract name to a dialect-specific type at execution time.
_PY_TO_SQL = {
    str: "text",
    int: "integer",
    float: "real",
    bool: "boolean",
    bytes: "bytea",
    "UUID": "uuid",
    "datetime": "timestamptz",
    "date": "date",
    "time": "time",
    "Decimal": "numeric",
    "dict": "jsonb",
    "list": "jsonb",
}


def table(name):
    """Decorator marking a Pydantic model as a table named `name` (section 2.1): it sets the model's
    __tablename__ and returns the model unchanged."""
    def mark(model):
        model.__tablename__ = name
        return model
    return mark


def _is_optional(annotation):
    """True when the annotation is Optional / `X | None` (section 2.3). Pure."""
    if get_origin(annotation) is None:
        return False
    return type(None) in get_args(annotation)


def _unwrap_optional(annotation):
    """The non-None member of an Optional annotation, or the annotation unchanged (section 2.3). Pure."""
    if not _is_optional(annotation):
        return annotation
    return [arg for arg in get_args(annotation) if arg is not type(None)][0]


def _is_literal(annotation):
    """True when the annotation is a Literal (section 6.1). Pure."""
    return get_origin(annotation) is Literal


def _literal_values(annotation):
    """The members of a Literal annotation as strings (section 6.1). Pure."""
    return [str(arg) for arg in get_args(annotation)]


def _sql_type(annotation):
    """The abstract SQL type for a Python annotation (section 2.3); text when unknown. Pure."""
    if annotation in _PY_TO_SQL:
        return _PY_TO_SQL[annotation]
    return _PY_TO_SQL.get(getattr(annotation, "__name__", ""), "text")


def _quoted(value):
    """A string default as a quoted SQL literal (section 2.3). Pure."""
    return "'" + value + "'"


def _boolean(value):
    """A boolean default as a SQL literal (section 2.3). Pure."""
    return "TRUE" if value else "FALSE"


def _numeric(value):
    """A numeric default as a SQL literal (section 2.3). Pure."""
    return str(value)


# A Python default value rendered to its SQL literal, dispatched by the value's type (section 2.3).
_DEFAULT_SQL = {"str": _quoted, "bool": _boolean, "int": _numeric, "float": _numeric}


def _default_sql(value):
    """A Python default value as its SQL literal (section 2.3), or None for a type with no literal
    form. Pure."""
    renderer = _DEFAULT_SQL.get(type(value).__name__)
    return renderer(value) if renderer else None


def _field_meta(field_info):
    """The column metadata declared on a Pydantic field (section 2.3): the json_schema_extra keys and
    the field's default, when it has one. Pure."""
    meta = dict(getattr(field_info, "json_schema_extra", None) or {})
    default = getattr(field_info, "default", None)
    if default is not None and default is not PydanticUndefined:
        meta["_default"] = default
    return meta


def _column_from_field(annotation, field_info):
    """One Pydantic field to a Column (section 2.3): the SQL type from its annotation, nullability
    from Optional (or an explicit override), Literal values, and the Field metadata. Pure."""
    meta = _field_meta(field_info)
    inner = _unwrap_optional(annotation)
    column = {
        "type": meta.get("db_type") or _sql_type(inner),
        "nullable": meta["nullable"] if "nullable" in meta else _is_optional(annotation),
    }
    if _is_literal(inner):
        column["literal_values"] = _literal_values(inner)
    if meta.get("primary") or meta.get("primary_key"):
        column["primary_key"] = True
    for key in ("unique", "references", "on_delete", "on_update", "check", "renamed_from"):
        if meta.get(key):
            column[key] = meta[key]
    if meta.get("default"):
        column["default"] = meta["default"]
    elif _default_sql(meta.get("_default")) is not None:
        column["default"] = _default_sql(meta["_default"])
    return column


def _table_extras(model, columns):
    """The table-level primary key, indexes, and constraints declared on a model's Meta inner class
    (section 2.3). A composite primary key clears the per-column primary_key flags. Pure."""
    table_def = {"columns": columns}
    meta = getattr(model, "Meta", None)
    if getattr(meta, "primary_key", None):
        table_def["primary_key"] = list(meta.primary_key)
        for column in columns.values():
            column.pop("primary_key", None)
    if getattr(meta, "indexes", None):
        table_def["indexes"] = meta.indexes
    if getattr(meta, "constraints", None):
        table_def["constraints"] = meta.constraints
    return table_def


def _model_to_table(model):
    """A @table-decorated Pydantic model to (table_name, Table) (section 2.1). get_type_hints resolves
    string annotations (PEP 563) to real types, so a field's declared type is never lost. Pure."""
    hints = get_type_hints(model)
    fields = getattr(model, "model_fields", {})
    columns = {
        name: _column_from_field(annotation, fields.get(name))
        for name, annotation in hints.items()
        if not name.startswith("_")
    }
    return model.__tablename__, _table_extras(model, columns)


def load_schema_from_models(*models):
    """Read @table-decorated Pydantic models to a Schema (section 2.1): field types, Literal
    annotations, and Field metadata become Column definitions. Pure — no I/O, no database. A
    hand-written Schema dict is equally valid (section 2.2); this is the idiomatic convenience."""
    schema = {}
    for model in models:
        name, table_def = _model_to_table(model)
        schema[name] = table_def
    return schema
