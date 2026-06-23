"""SQL literal rendering for the schema loaders (section 2): a host-language default value to its SQL
literal form, shared by the Pydantic loader (loader.py) and the Django loader (django_loader.py).

Pure and dependency-free — neither Pydantic nor Django is imported, so the pure core can hold this
even though it never holds the loaders themselves. Mapping a value to its type is the one
introspective step, so HC-P005 is disabled here as in the loaders.
"""
# honest: disable HC-P005


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


def default_sql(value):
    """A Python default value as its SQL literal (section 2.3), or None for a type with no literal
    form (including a callable default). Pure."""
    renderer = _DEFAULT_SQL.get(type(value).__name__)
    return renderer(value) if renderer else None
