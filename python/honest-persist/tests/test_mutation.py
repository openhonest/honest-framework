"""Tests for guarded mutations + transactions."""
import pytest

from honest_persist import (
    compile_query,
    connect,
    define_column,
    define_schema,
    define_table,
    execute,
    execute_mutation,
    guarded_mutation,
    in_transaction,
    migrate_schema,
)


def _setup():
    conn = connect(":memory:")
    migrate_schema(conn, define_schema("app", [
        define_table("orders", [
            define_column("id", "TEXT", primary_key=True),
            define_column("status", "TEXT", default="pending"),
            define_column("amount", "INTEGER", default=0),
        ]),
    ]))
    conn.execute("INSERT INTO orders VALUES ('o1', 'pending', 100)")
    conn.execute("INSERT INTO orders VALUES ('o2', 'pending', 200)")
    return conn


def test_guarded_insert_ok():
    conn = _setup()
    m = guarded_mutation(
        "orders",
        insert_values={"id": "o3", "status": "pending", "amount": 50},
        expected_rows=1,
    )
    r = execute_mutation(conn, m)
    assert r["ok"] is True
    assert r["rowcount"] == 1


def test_guarded_update_ok():
    conn = _setup()
    m = guarded_mutation(
        "orders",
        set_values={"status": "paid"},
        where={"id": "o1"},
        expected_rows=1,
    )
    r = execute_mutation(conn, m)
    assert r["ok"] is True
    rows = execute(conn, compile_query("orders", where={"id": "o1"}))
    assert rows[0]["status"] == "paid"


def test_guarded_delete_ok():
    conn = _setup()
    m = guarded_mutation("orders", delete=True, where={"id": "o2"},
                         expected_rows=1)
    r = execute_mutation(conn, m)
    assert r["ok"] is True


def test_guard_mismatch_rolls_back():
    conn = _setup()
    m = guarded_mutation(
        "orders",
        set_values={"status": "paid"},
        where={"id": "nonexistent"},
        expected_rows=1,
    )
    r = execute_mutation(conn, m)
    assert r["ok"] is False
    assert r["err_code"] == "guard_mismatch"
    # original rows unchanged
    rows = execute(conn, compile_query("orders", where={"id": "o1"}))
    assert rows[0]["status"] == "pending"


def test_guarded_mutation_requires_one_kind():
    with pytest.raises(ValueError, match="exactly one"):
        guarded_mutation("orders")
    with pytest.raises(ValueError, match="exactly one"):
        guarded_mutation("orders", set_values={"x": 1}, insert_values={"y": 2})


def test_in_transaction_commits():
    conn = _setup()
    with in_transaction(conn):
        conn.execute("INSERT INTO orders VALUES ('o9', 'pending', 1)")
    rows = execute(conn, compile_query("orders", where={"id": "o9"}))
    assert len(rows) == 1


def test_in_transaction_rolls_back_on_exception():
    conn = _setup()
    with pytest.raises(RuntimeError):
        with in_transaction(conn):
            conn.execute("INSERT INTO orders VALUES ('o9', 'pending', 1)")
            raise RuntimeError("bail")
    rows = execute(conn, compile_query("orders", where={"id": "o9"}))
    assert rows == []
