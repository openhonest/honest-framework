"""Tests for schema definition + migration diff."""
from honest_persist import (
    connect,
    define_column,
    define_schema,
    define_table,
    diff_schema,
    inspect_schema,
    migrate_schema,
)


def test_diff_creates_missing_table():
    declared = define_schema("app", [
        define_table("orders", [
            define_column("id", "TEXT", primary_key=True),
            define_column("status", "TEXT", default="pending"),
        ]),
    ])
    live = define_schema("live", [])  # empty
    ops = diff_schema(declared, live)
    assert len(ops) == 1
    assert ops[0]["kind"] == "create_table"
    assert ops[0]["target"] == "orders"


def test_diff_adds_missing_column():
    declared = define_schema("app", [
        define_table("orders", [
            define_column("id", "TEXT", primary_key=True),
            define_column("status", "TEXT"),
            define_column("amount", "INTEGER"),
        ]),
    ])
    live = define_schema("live", [
        define_table("orders", [
            define_column("id", "TEXT", primary_key=True),
            define_column("status", "TEXT"),
        ]),
    ])
    ops = diff_schema(declared, live)
    assert len(ops) == 1
    assert ops[0]["kind"] == "add_column"
    assert ops[0]["detail"]["column"]["name"] == "amount"


def test_migrate_applies_ops():
    conn = connect(":memory:")
    declared = define_schema("app", [
        define_table("orders", [
            define_column("id", "TEXT", primary_key=True),
            define_column("status", "TEXT", default="pending"),
        ]),
    ])
    applied = migrate_schema(conn, declared)
    assert applied == 1
    live = inspect_schema(conn)
    assert [t["name"] for t in live["tables"]] == ["orders"]


def test_migrate_is_idempotent():
    conn = connect(":memory:")
    declared = define_schema("app", [
        define_table("orders", [
            define_column("id", "TEXT", primary_key=True),
        ]),
    ])
    migrate_schema(conn, declared)
    assert migrate_schema(conn, declared) == 0
