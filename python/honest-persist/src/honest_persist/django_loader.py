"""Django interop (section 2): read Django model definitions to a Schema.

The Django counterpart to the Pydantic loader (loader.py): the idiomatic way for a Django codebase to
produce a Schema dict, reading each model's fields through Django's `_meta` API — field types,
nullability, primary keys, uniqueness, `choices` (an enum), foreign-key targets, and defaults. Pure —
no I/O, no database — and an optional adapter installed via honest-persist[django]; the pure core
never imports Django, and a hand-written Schema dict is equally valid (section 2.2). Reading Django's
field objects is introspective, so HC-P005 is disabled for this file alone, as in the Pydantic loader.
"""

from honest_persist.host_defaults import default_sql

# Django internal field type to abstract SQL type (section 2.3). The applier resolves the abstract
# name to a dialect-specific type at execution time.
_DJANGO_TO_SQL = {
    "CharField": "text",
    "TextField": "text",
    "SlugField": "text",
    "EmailField": "text",
    "AutoField": "integer",
    "BigAutoField": "integer",
    "SmallAutoField": "integer",
    "IntegerField": "integer",
    "BigIntegerField": "integer",
    "SmallIntegerField": "integer",
    "PositiveIntegerField": "integer",
    "PositiveSmallIntegerField": "integer",
    "FloatField": "real",
    "BooleanField": "boolean",
    "UUIDField": "uuid",
    "DateTimeField": "timestamptz",
    "DateField": "date",
    "TimeField": "time",
    "DecimalField": "numeric",
    "BinaryField": "bytea",
    "JSONField": "jsonb",
}


def _dj_type(field):
    """The abstract SQL type for a Django field (section 2.3): a foreign key takes its target field's
    type, and an unknown field falls back to text. Pure."""
    if field.is_relation:
        return _dj_type(field.target_field)
    return _DJANGO_TO_SQL.get(field.get_internal_type(), "text")


def _dj_choices(field):
    """The enum members of a Django field's `choices` as strings (section 6.1), or empty. Pure."""
    return [str(value) for value, label in field.choices] if field.choices else []


def _dj_reference(field):
    """The `table.column` a Django foreign key points at (section 2.3): the related model's table and
    primary-key column. Pure."""
    target = field.related_model._meta
    return target.db_table + "." + target.pk.column


def _dj_default(field):
    """A Django field's default as a SQL literal (section 2.3), or None when it has no value default
    — none declared, or a callable default carries no literal form. Pure."""
    return default_sql(field.default) if field.has_default() else None


def _dj_column(field):
    """One Django field to a Column (section 2.3): type, nullability, primary key, uniqueness, enum
    choices, foreign-key reference, and default. A primary key's implicit uniqueness is left to the
    primary_key flag rather than duplicated. Pure."""
    column = {"type": _dj_type(field), "nullable": bool(field.null)}
    if field.primary_key:
        column["primary_key"] = True
    if field.unique and not field.primary_key:
        column["unique"] = True
    choices = _dj_choices(field)
    if choices:
        column["literal_values"] = choices
    if field.is_relation:
        column["references"] = _dj_reference(field)
    default = _dj_default(field)
    if default is not None:
        column["default"] = default
    return column


def load_schema_from_django(*models):
    """Read Django model definitions to a Schema (section 2): each model's table name and its concrete
    fields become a table of columns, keyed by Django's db column names. Pure — no I/O, no database.
    A hand-written Schema dict is equally valid (section 2.2); this is the idiomatic convenience."""
    schema = {}
    for model in models:
        meta = model._meta
        schema[meta.db_table] = {"columns": {field.column: _dj_column(field) for field in meta.fields}}
    return schema
