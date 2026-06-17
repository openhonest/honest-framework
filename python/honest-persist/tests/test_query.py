"""Tests for query compilation + execution."""
from honest_persist import (
    compile_query,
    connect,
    define_column,
    define_schema,
    define_table,
    execute,
    migrate_schema,
)


def _setup():
    conn = connect(":memory:")
    migrate_schema(conn, define_schema("app", [
        define_table("users", [
            define_column("id", "TEXT", primary_key=True),
            define_column("email", "TEXT"),
        ]),
    ]))
    conn.execute("INSERT INTO users VALUES ('u1', 'a@b.co')")
    conn.execute("INSERT INTO users VALUES ('u2', 'c@d.co')")
    return conn


def test_compile_query_select_all():
    q = compile_query("users")
    assert q["sql"] == "SELECT * FROM users"
    assert q["params"] == []


def test_compile_query_where_limit_order():
    q = compile_query("users", columns=["id"], where={"email": "a@b.co"},
                       order_by="id", limit=10)
    assert "WHERE email = ?" in q["sql"]
    assert "ORDER BY id" in q["sql"]
    assert "LIMIT 10" in q["sql"]
    assert q["params"] == ["a@b.co"]


def test_execute_returns_rows():
    conn = _setup()
    rows = execute(conn, compile_query("users", where={"id": "u1"}))
    assert rows == [{"id": "u1", "email": "a@b.co"}]


def test_execute_empty_result():
    conn = _setup()
    rows = execute(conn, compile_query("users", where={"id": "nope"}))
    assert rows == []
