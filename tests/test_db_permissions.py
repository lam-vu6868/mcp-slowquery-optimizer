"""
tests/test_db_permissions.py
----------------------------

CHỨC NĂNG :
    Test tích hợp (cần MySQL đang chạy) kiểm tra quyền thật của 2 tài khoản:
      - readonly_user : chỉ đọc. Mọi DDL/DML/GRANT/SET GLOBAL phải bị từ chối.
      - index_admin   : chỉ thao tác INDEX. Không DROP TABLE/DELETE/UPDATE/INSERT.

PHỤ TRÁCH  : Tình    |    REVIEW: Hải

CÁCH CHẠY:
    docker compose up -d
    pytest tests/test_db_permissions.py -v -m integration

    Không kết nối được MySQL -> toàn bộ test tự SKIP (CI không cần DB).

AN TOÀN:
    Mọi lệnh ghi đều nhắm vào bảng KHÔNG TỒN TẠI (__perm_probe__). MySQL kiểm
    quyền trước khi kiểm bảng có tồn tại hay không, nên:
      - mã 1142/1044/1227/1045  -> bị từ chối vì thiếu quyền   (đúng mong đợi)
      - mã 1146/1051/1050       -> qua được bước kiểm quyền     (=> CÓ QUYỀN, test FAIL)
    Không đụng tới dữ liệu thật.

BIẾN MÔI TRƯỜNG (.env): DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
    DB_ADMIN_USER, DB_ADMIN_PASSWORD.
    LƯU Ý: docker-compose.yml map cổng 3307:3306 trong khi .env.example ghi
    DB_PORT=3306 -> nếu chạy MySQL bằng docker compose, đặt DB_PORT=3307.
"""

from __future__ import annotations

import os

import pytest

pymysql = pytest.importorskip("pymysql")

try:  # đọc .env nếu có python-dotenv
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

pytestmark = pytest.mark.integration

DENIED_CODES = {
    1044,  # ER_DBACCESS_DENIED_ERROR
    1045,  # ER_ACCESS_DENIED_ERROR
    1142,  # ER_TABLEACCESS_DENIED_ERROR (command denied to user for table)
    1143,  # ER_COLUMNACCESS_DENIED_ERROR
    1227,  # ER_SPECIFIC_ACCESS_DENIED_ERROR (cần SUPER / SYSTEM_VARIABLES_ADMIN...)
    1410,  # ER_CANT_CREATE_USER_WITH_GRANT (không được GRANT)
    3540,  # ER_DB_ACCESS_DENIED (MySQL 8, một số lệnh)
}
PROBE = "__perm_probe__"


def _cfg(user_key: str, pass_key: str, default_user: str, default_pass: str) -> dict:
    return {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "3307")),
        "user": os.getenv(user_key, default_user),
        "password": os.getenv(pass_key, default_pass),
        "database": os.getenv("DB_NAME", "shopdb"),
        "connect_timeout": 3,
        "autocommit": True,
    }


def _connect(cfg: dict):
    try:
        return pymysql.connect(**cfg)
    except pymysql.err.OperationalError as exc:
        pytest.skip(f"Không kết nối được MySQL bằng {cfg['user']}@{cfg['host']}:{cfg['port']} ({exc.args[0]})")


@pytest.fixture(scope="module")
def readonly_conn():
    conn = _connect(_cfg("DB_USER", "DB_PASSWORD", "readonly_user", "readonly_pass"))
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def admin_conn():
    conn = _connect(_cfg("DB_ADMIN_USER", "DB_ADMIN_PASSWORD", "index_admin", "admin_pass"))
    yield conn
    conn.close()


def _assert_denied(conn, sql: str) -> None:
    """Lệnh phải bị từ chối VÌ THIẾU QUYỀN (không phải vì lỗi khác)."""

    with conn.cursor() as cur:
        with pytest.raises(pymysql.MySQLError) as info:
            cur.execute(sql)
    code = info.value.args[0]
    assert code in DENIED_CODES, (
        f"`{sql}` không bị chặn bởi phân quyền (mã lỗi {code}: {info.value.args[1]}). "
        "Có thể tài khoản đang CÓ quyền này."
    )


def _grants(conn) -> str:
    with conn.cursor() as cur:
        cur.execute("SHOW GRANTS FOR CURRENT_USER()")
        return "\n".join(row[0] for row in cur.fetchall()).upper()


# ---------------------------------------------------------------------------
# readonly_user (Tool 1-5)
# ---------------------------------------------------------------------------


def test_readonly_can_select(readonly_conn):
    with readonly_conn.cursor() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1
        cur.execute("SHOW TABLES")  # liệt kê bảng thực nghiệm được
        cur.fetchall()


def test_readonly_can_read_performance_schema(readonly_conn):
    """Tool 1 cần đọc events_statements_summary_by_digest."""

    with readonly_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM performance_schema.events_statements_summary_by_digest")
        assert cur.fetchone()[0] >= 0


@pytest.mark.parametrize(
    "sql",
    [
        f"CREATE TABLE {PROBE} (id INT)",
        f"DROP TABLE {PROBE}",
        f"TRUNCATE TABLE {PROBE}",
        f"ALTER TABLE {PROBE} ADD COLUMN x INT",
        f"CREATE INDEX idx_probe ON {PROBE} (id)",
        f"DROP INDEX idx_probe ON {PROBE}",
        f"INSERT INTO {PROBE} (id) VALUES (1)",
        f"UPDATE {PROBE} SET id = 1",
        f"DELETE FROM {PROBE}",
    ],
)
def test_readonly_cannot_write(readonly_conn, sql):
    _assert_denied(readonly_conn, sql)


def test_readonly_cannot_read_mysql_user(readonly_conn):
    _assert_denied(readonly_conn, "SELECT user, authentication_string FROM mysql.user")


def test_readonly_cannot_change_global_variables(readonly_conn):
    # Gán lại đúng giá trị hiện tại: nếu lỡ có quyền thì cũng không đổi gì.
    _assert_denied(readonly_conn, "SET GLOBAL long_query_time = @@global.long_query_time")


def test_readonly_cannot_grant(readonly_conn):
    _assert_denied(readonly_conn, "GRANT SELECT ON shopdb.* TO 'readonly_user'@'%'")


def test_readonly_cannot_read_files(readonly_conn):
    """Không có quyền FILE -> LOAD_FILE trả NULL."""

    with readonly_conn.cursor() as cur:
        cur.execute("SELECT LOAD_FILE('/etc/hostname')")
        assert cur.fetchone()[0] is None


def test_readonly_grants_have_no_write_privileges(readonly_conn):
    grants = _grants(readonly_conn)
    for priv in ("INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "INDEX", "FILE", "SUPER", "ALL PRIVILEGES"):
        assert f" {priv}" not in grants and f",{priv}" not in grants, f"readonly_user đang có quyền {priv}:\n{grants}"


# ---------------------------------------------------------------------------
# index_admin (chỉ Tool 6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        f"CREATE TABLE {PROBE} (id INT)",
        f"DROP TABLE {PROBE}",
        f"TRUNCATE TABLE {PROBE}",
        f"INSERT INTO {PROBE} (id) VALUES (1)",
        f"UPDATE {PROBE} SET id = 1",
        f"DELETE FROM {PROBE}",
        "CREATE DATABASE __perm_probe_db__",
        "SET GLOBAL long_query_time = @@global.long_query_time",
        "SELECT user FROM mysql.user",
    ],
)
def test_index_admin_cannot_touch_data_or_schema(admin_conn, sql):
    _assert_denied(admin_conn, sql)


def test_index_admin_has_index_privilege(admin_conn):
    assert "INDEX" in _grants(admin_conn)


@pytest.mark.xfail(
    reason=(
        "RỦI RO ĐÃ XÁC NHẬN (05/10, MySQL 8.0): init.sql cấp ALTER cho index_admin "
        "(cần cho ALTER INDEX ... VISIBLE), nên index_admin chạy được "
        "ALTER TABLE orders DROP COLUMN status -> mất dữ liệu. "
        "Bù lại: Tool 6 không nhận SQL tự do, chỉ chạy DDL do server sinh. "
        "Cần nhóm quyết định (xem báo cáo tuần 2 của Tình)."
    ),
    strict=False,
)
def test_index_admin_has_no_alter_privilege(admin_conn):
    grants = _grants(admin_conn)
    assert " ALTER" not in grants and ",ALTER" not in grants
