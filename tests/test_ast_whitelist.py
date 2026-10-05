"""
tests/test_ast_whitelist.py
---------------------------

CHỨC NĂNG :
    Test đơn vị cho AST whitelist v1. Mỗi quy tắc ở ROADMAP mục 2.2 có ít nhất
    một ca BỊ CHẶN (kiểm cả mã `rule`) và các ca hợp lệ tương ứng để chống
    chặn nhầm.

PHỤ TRÁCH  : Tình    |    REVIEW: Vũ

CHẠY      : pytest tests/test_ast_whitelist.py -v
"""

import pytest

from security.ast_whitelist import SQLRejected, check, is_allowed_sql, validate_sql


def _rule_of(sql, **kwargs):
    with pytest.raises(SQLRejected) as info:
        validate_sql(sql, **kwargs)
    assert is_allowed_sql(sql, **kwargs) is False
    return info.value.rule


# ---------------------------------------------------------------------------
# 1. Câu hợp lệ: KHÔNG được chặn nhầm (whitelist quá chặt thì LLM không dùng được)
# ---------------------------------------------------------------------------

VALID_SQL = [
    "SELECT * FROM orders WHERE status = 'paid' LIMIT 10",
    "select id from orders",
    "SELECT * FROM sales_data WHERE order_date >= '2024-11-01' AND order_priority = 'H'",
    "SELECT region, SUM(total_revenue) FROM sales_data GROUP BY region ORDER BY 2 DESC",
    "SELECT o.id FROM orders o JOIN users u ON u.id = o.user_id WHERE u.id = 5",
    "SELECT * FROM orders WHERE id IN (SELECT order_id FROM order_items WHERE qty > 3)",
    "SELECT * FROM orders o WHERE NOT EXISTS (SELECT 1 FROM payments p WHERE p.order_id = o.id)",
    "WITH t AS (SELECT user_id FROM orders) SELECT COUNT(*) FROM t",
    "SELECT id FROM orders UNION SELECT id FROM users",
    "(SELECT 1) UNION (SELECT 2)",
    "SELECT * FROM shopdb.orders",
    "SELECT DATE(created_at) FROM orders",
    "SELECT * FROM orders WHERE note = 'a;b'",                  # ; trong chuỗi
    "SELECT * FROM users WHERE name = 'Nguyễn Hữu Tình'",       # Unicode trong chuỗi
    "SELECT * FROM orders WHERE note = 'into the void'",       # từ khóa trong chuỗi
    "SELECT * FROM orders WHERE note = 'sleep(5)'",             # tên hàm trong chuỗi
    "SELECT /*+ MAX_EXECUTION_TIME(1000) */ * FROM orders",     # optimizer hint
    "SELECT * FROM orders -- comment thường\n WHERE id = 1",
    "  SELECT 1  ",
]


@pytest.mark.parametrize("sql", VALID_SQL)
def test_valid_select_is_allowed(sql):
    assert is_allowed_sql(sql) is True
    assert validate_sql(sql) == sql.strip()


@pytest.mark.parametrize(
    "sql",
    [
        "EXPLAIN SELECT * FROM orders WHERE created_at > '2024-01-01'",
        "EXPLAIN FORMAT=JSON SELECT * FROM orders WHERE status = 'paid'",
        "explain format = tree SELECT id FROM orders",
        "EXPLAIN SELECT id FROM orders UNION SELECT id FROM users",
    ],
)
def test_explain_select_is_allowed(sql):
    assert is_allowed_sql(sql) is True


# ---------------------------------------------------------------------------
# 2. Từng quy tắc
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [None, 123, b"SELECT 1", ["SELECT 1"]])
def test_rule_not_string(value):
    assert _rule_of(value) == "not_string"


@pytest.mark.parametrize("sql", ["", "   ", "\n\t"])
def test_rule_empty(sql):
    assert _rule_of(sql) == "empty"


def test_rule_too_long():
    sql = "SELECT 1 FROM orders WHERE id IN (" + ",".join(["1"] * 10_000) + ")"
    assert _rule_of(sql) == "too_long"


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT /*!50000 SLEEP(5) */ 1",
        "SELECT /*!50000 DROP TABLE users */ 1",
        "SELECT /*! UNION SELECT password FROM users */ 1",
        "SELECT /*M!100000 1 */",
        "SELECT /* ! */ 1",  # vẫn từ chối: thà chặn nhầm còn hơn bỏ lọt
    ],
)
def test_rule_exec_comment(sql):
    assert _rule_of(sql) in {"exec_comment"}


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM ordеrs WHERE id = 1",        # 'е' Cyrillic
        "SELECT * FROM `ordеrs` WHERE id = 1",      # homoglyph trong backtick
        "ＳＥＬＥＣＴ * FROM orders",                 # chữ full-width
        "SELECT * FROM orders WHERE іd = 1",        # 'і' Ukraina
    ],
)
def test_rule_non_ascii_code(sql):
    assert _rule_of(sql) in {"non_ascii_code", "parse_error"}


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1; DROP TABLE users;",
        "SELECT * FROM orders WHERE status = 'paid'; DROP TABLE users",
        "SELECT 1;",
        "SELECT 1 ; SELECT 2",
    ],
)
def test_rule_multi_statement(sql):
    assert _rule_of(sql) == "multi_statement"


@pytest.mark.parametrize("sql", ["SELECT FROM", "SELECT * FROM WHERE", "SELEC 1 FROM t", "SELECT (1"])
def test_rule_parse_error_fail_closed(sql):
    assert _rule_of(sql) in {"parse_error", "statement_type"}


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE users",
        "DELETE FROM orders",
        "UPDATE orders SET status = 'x'",
        "INSERT INTO orders (id) VALUES (1)",
        "CREATE INDEX idx_x ON orders (status)",
        "ALTER TABLE orders ADD COLUMN x INT",
        "TRUNCATE TABLE orders",
        "GRANT ALL ON *.* TO 'x'@'%'",
        "SET GLOBAL slow_query_log = 'OFF'",
        "SHOW TABLES",
        "CALL some_proc()",
        "DO SLEEP(5)",
        "HANDLER orders OPEN",
        "LOAD DATA INFILE '/tmp/x' INTO TABLE orders",
        "TABLE orders",
        "VALUES ROW(1, 2)",
        "EXPLAIN DELETE FROM orders",
        "EXPLAIN UPDATE orders SET status = 'x'",
        "EXPLAIN FORMAT=XML SELECT 1",
        "EXPLAIN",
        "DESCRIBE orders",
        "EXPLAIN FOR CONNECTION 12",
    ],
)
def test_rule_statement_type(sql):
    assert _rule_of(sql) in {"statement_type", "parse_error", "into_clause", "variable", "forbidden_func"}


@pytest.mark.parametrize(
    "sql",
    [
        "EXPLAIN ANALYZE SELECT * FROM orders",
        "explain analyze select 1",
        "EXPLAIN ANALYZE FORMAT=TREE SELECT * FROM orders",
    ],
)
def test_rule_explain_analyze(sql):
    assert _rule_of(sql) == "explain_analyze"


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM orders INTO OUTFILE '/tmp/orders.csv'",
        "SELECT * FROM orders INTO DUMPFILE '/tmp/x'",
        "SELECT id INTO @x FROM orders LIMIT 1",
        "SELECT * FROM orders WHERE id = 1 into outfile '/var/lib/mysql-files/a'",
    ],
)
def test_rule_into_clause(sql):
    assert _rule_of(sql) in {"into_clause", "variable"}


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM orders WHERE id = 1 FOR UPDATE",
        "SELECT * FROM orders WHERE id = 1 FOR SHARE",
        "SELECT * FROM orders WHERE id = 1 LOCK IN SHARE MODE",
        "SELECT * FROM orders FOR UPDATE NOWAIT",
        "SELECT * FROM (SELECT * FROM orders FOR UPDATE) t",
    ],
)
def test_rule_locking_read(sql):
    assert _rule_of(sql) == "locking_read"


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT SLEEP(5)",
        "SELECT sleep (5)",
        "SELECT `sleep`(5)",
        "SELECT * FROM orders WHERE id = 1 AND SLEEP(3) = 0",
        "SELECT BENCHMARK(1000000, MD5('a'))",
        "SELECT GET_LOCK('a', 10)",
        "SELECT RELEASE_LOCK('a')",
        "SELECT LOAD_FILE('/etc/passwd')",
        "SELECT sys_exec('rm -rf /')",
        "SELECT * FROM orders WHERE id IN (SELECT SLEEP(1))",
        "SELECT MASTER_POS_WAIT('log', 4)",
    ],
)
def test_rule_forbidden_func(sql):
    assert _rule_of(sql) == "forbidden_func"


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT @@version",
        "SELECT @@global.secure_file_priv",
        "SELECT @a := 1",
        "SELECT * FROM orders WHERE id = @x",
    ],
)
def test_rule_variable(sql):
    assert _rule_of(sql) == "variable"


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM mysql.user",
        "SELECT user, authentication_string FROM MySQL.user",
        "SELECT * FROM performance_schema.events_statements_summary_by_digest",
        "SELECT * FROM information_schema.tables",
        "SELECT * FROM sys.schema_unused_indexes",
        "SELECT * FROM orders WHERE id IN (SELECT 1 FROM mysql.user)",
        "SELECT * FROM `mysql`.`user`",
        "EXPLAIN SELECT * FROM mysql.user",
        "WITH x AS (SELECT * FROM information_schema.columns) SELECT * FROM x",
    ],
)
def test_rule_system_schema(sql):
    assert _rule_of(sql) == "system_schema"


def test_rule_schema_not_allowed():
    assert _rule_of("SELECT * FROM otherdb.secrets", allowed_schemas={"shopdb"}) == "schema_not_allowed"
    assert is_allowed_sql("SELECT * FROM shopdb.orders", allowed_schemas={"shopdb"}) is True
    assert is_allowed_sql("SELECT * FROM SHOPDB.orders", allowed_schemas={"shopdb"}) is True
    # không có tiền tố schema -> dùng schema mặc định của kết nối (shopdb)
    assert is_allowed_sql("SELECT * FROM orders", allowed_schemas={"shopdb"}) is True


# ---------------------------------------------------------------------------
# 3. API check() theo api-contract
# ---------------------------------------------------------------------------


def test_check_returns_dict_on_success():
    result = check(" SELECT 1 ")
    assert result == {"ok": True, "sql": "SELECT 1", "rule": None, "message": None}


def test_check_returns_rule_on_reject():
    result = check("SELECT 1; DROP TABLE users")
    assert result["ok"] is False
    assert result["sql"] is None
    assert result["rule"] == "multi_statement"
    assert result["message"]


def test_check_never_raises():
    for value in [None, 1, "", "SELECT FROM", "\x00"]:
        assert check(value)["ok"] is False


def test_rejected_is_value_error_for_backward_compat():
    with pytest.raises(ValueError):
        validate_sql("DROP TABLE users")
