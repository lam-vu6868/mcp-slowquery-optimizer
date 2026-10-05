import pytest

from security.ast_whitelist import is_allowed_sql, validate_sql


def test_select_is_allowed():
    sql = "SELECT * FROM orders WHERE status = 'paid' LIMIT 10"
    assert is_allowed_sql(sql) is True
    assert validate_sql(sql) == sql.strip()


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1; DROP TABLE users;",
        "SELECT /*!50000 SLEEP(5) */ 1",
        "SELECT * FROM orders INTO OUTFILE '/tmp/orders.csv'",
        "SELECT * FROM orders WHERE id = 1 FOR UPDATE",
        "SELECT BENCHMARK(1000000, SLEEP(1))",
        "SELECT * FROM mysql.user",
        "SELECT * FROM performance_schema.events_statements_summary_by_digest",
    ],
)
def test_rejects_dangerous_sql(sql):
    with pytest.raises(ValueError):
        validate_sql(sql)
    assert is_allowed_sql(sql) is False


def test_rejects_unparseable_sql():
    with pytest.raises(ValueError):
        validate_sql("SELECT FROM")


def test_explain_is_allowed():
    sql = "EXPLAIN SELECT * FROM orders WHERE created_at > '2024-01-01'"
    assert is_allowed_sql(sql) is True
    assert validate_sql(sql) == sql.strip()
