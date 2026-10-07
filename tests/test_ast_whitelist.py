"""
tests/test_ast_whitelist.py
---------------------------

CHỨC NĂNG :
    Test AST whitelist: mỗi quy tắc chặn có ít nhất 1 test.

PHỤ TRÁCH  : Tình    |    REVIEW: Vũ

LƯU Ý:
    - Cần cả test 'được phép' (SELECT hợp lệ) lẫn test 'bị chặn'.
    - Phải có test cho: multi-statement, /*!...*/, INTO OUTFILE, SLEEP, FOR UPDATE, parse lỗi.

THAM KHẢO  : security/ast_whitelist.py

TRẠNG THÁI : KHUNG RỖNG — chưa cài đặt. Xóa dòng này khi bắt đầu code.
"""
"""
tests/test_ast_whitelist.py
---------------------------
CHỨC NĂNG: Test AST whitelist.
PHỤ TRÁCH: Tình    |    REVIEW: Vũ
"""
import pytest
from security.ast_whitelist import check


# ============================================================
# NHÓM 1: SQL ĐƯỢC PHÉP
# ============================================================

class TestAllowed:
    """Nhóm test câu SQL phải được CHẤP NHẬN"""

    def test_simple_select(self):
        ok, _ = check("SELECT * FROM sales_data")
        assert ok is True

    def test_select_with_where(self):
        ok, _ = check("SELECT id, region FROM sales_data WHERE region = 'Asia'")
        assert ok is True

    def test_select_with_join(self):
        ok, _ = check("""
            SELECT s1.id, s2.region 
            FROM sales_data s1 
            JOIN sales_data s2 ON s2.region = s1.region
        """)
        assert ok is True

    def test_select_with_aggregate(self):
        ok, _ = check("SELECT COUNT(*), SUM(total_revenue) FROM sales_data")
        assert ok is True

    def test_select_with_order_by(self):
        ok, _ = check("SELECT * FROM sales_data ORDER BY order_date DESC LIMIT 100")
        assert ok is True

    def test_explain(self):
        ok, _ = check("EXPLAIN SELECT * FROM sales_data")
        assert ok is True

    def test_explain_format_json(self):
        ok, _ = check("EXPLAIN FORMAT=JSON SELECT * FROM sales_data")
        assert ok is True

    def test_create_index_simple(self):
        ok, _ = check("CREATE INDEX idx_region ON sales_data(region)")
        assert ok is True

    def test_create_index_composite(self):
        ok, _ = check("CREATE INDEX idx_x ON sales_data(region, order_date)")
        assert ok is True

    def test_union(self):
        ok, _ = check("SELECT 1 UNION SELECT 2")
        assert ok is True

    def test_trailing_semicolon(self):
        """Dấu `;` ở cuối câu là hợp lệ"""
        ok, _ = check("SELECT * FROM sales_data;")
        assert ok is True


# ============================================================
# NHÓM 2: MULTI-STATEMENT
# ============================================================

class TestMultiStatement:
    """Nhóm test multi-statement phải BỊ CHẶN"""

    def test_select_then_drop(self):
        ok, reason = check("SELECT 1; DROP TABLE sales_data")
        assert ok is False
        assert "Multi-statement" in reason

    def test_select_then_delete(self):
        ok, reason = check("SELECT * FROM sales_data; DELETE FROM sales_data")
        assert ok is False
        assert "Multi-statement" in reason

    def test_select_then_insert(self):
        ok, reason = check("SELECT 1; INSERT INTO sales_data VALUES (1,2,3)")
        assert ok is False
        assert "Multi-statement" in reason


# ============================================================
# NHÓM 3: LỆNH DDL/DML NGUY HIỂM
# ============================================================

class TestDangerousStatements:
    """Nhóm test DDL/DML phải BỊ CHẶN"""

    def test_drop_table(self):
        ok, reason = check("DROP TABLE sales_data")
        assert ok is False

    def test_drop_database(self):
        ok, _ = check("DROP DATABASE shopdb")
        assert ok is False

    def test_delete(self):
        ok, _ = check("DELETE FROM sales_data WHERE id = 1")
        assert ok is False

    def test_delete_all(self):
        ok, _ = check("DELETE FROM sales_data")
        assert ok is False

    def test_update(self):
        ok, _ = check("UPDATE sales_data SET region = 'X' WHERE id = 1")
        assert ok is False

    def test_insert(self):
        ok, _ = check("INSERT INTO sales_data VALUES (1, 2, 3)")
        assert ok is False

    def test_truncate(self):
        ok, _ = check("TRUNCATE TABLE sales_data")
        assert ok is False

    def test_alter_table(self):
        ok, _ = check("ALTER TABLE sales_data ADD COLUMN test INT")
        assert ok is False

    def test_grant(self):
        ok, _ = check("GRANT ALL ON shopdb.* TO 'hacker'@'%'")
        assert ok is False

    def test_create_user(self):
        ok, _ = check("CREATE USER 'hacker'@'%' IDENTIFIED BY 'x'")
        assert ok is False


# ============================================================
# NHÓM 4: EXECUTABLE COMMENT
# ============================================================

class TestExecutableComment:
    """Nhóm test executable comment /*! ... */ và /*M! ... */"""

    def test_executable_comment_with_drop(self):
        ok, reason = check("/*!50000 DROP TABLE sales_data */")
        assert ok is False
        assert "Executable comment" in reason

    def test_executable_comment_lowercase(self):
        ok, _ = check("/*!50000 drop table sales_data */")
        assert ok is False

    def test_executable_comment_m_style(self):
        ok, _ = check("/*M!100100 DROP TABLE sales_data */")
        assert ok is False

    def test_regular_comment_ok(self):
        """Comment thường (không thực thi) thì được phép"""
        ok, _ = check("SELECT * FROM sales_data -- day la comment")
        assert ok is True

    def test_block_comment_ok(self):
        """Block comment thường OK"""
        ok, _ = check("SELECT /* comment */ * FROM sales_data")
        assert ok is True


# ============================================================
# NHÓM 5: HÀM NGUY HIỂM
# ============================================================

class TestForbiddenFunctions:
    """Nhóm test hàm nguy hiểm"""

    def test_sleep(self):
        ok, reason = check("SELECT SLEEP(10)")
        assert ok is False
        assert "SLEEP" in reason.upper()

    def test_benchmark(self):
        ok, reason = check("SELECT BENCHMARK(1000000, MD5('x'))")
        assert ok is False

    def test_load_file(self):
        ok, _ = check("SELECT LOAD_FILE('/etc/passwd')")
        assert ok is False

    def test_get_lock(self):
        ok, _ = check("SELECT GET_LOCK('x', 10)")
        assert ok is False

    def test_release_lock(self):
        ok, _ = check("SELECT RELEASE_LOCK('x')")
        assert ok is False

    def test_sleep_inside_subquery(self):
        ok, _ = check("SELECT * FROM sales_data WHERE id = (SELECT SLEEP(5))")
        assert ok is False


# ============================================================
# NHÓM 6: INTO OUTFILE / FOR UPDATE
# ============================================================

class TestFileAndLock:
    """Nhóm test INTO OUTFILE, FOR UPDATE"""

    def test_into_outfile(self):
        ok, reason = check("SELECT * FROM sales_data INTO OUTFILE '/tmp/x'")
        assert ok is False
        assert "OUTFILE" in reason.upper()

    def test_into_dumpfile(self):
        ok, _ = check("SELECT * FROM sales_data INTO DUMPFILE '/tmp/x'")
        assert ok is False

    def test_for_update(self):
        ok, reason = check("SELECT * FROM sales_data FOR UPDATE")
        assert ok is False
        assert "FOR UPDATE" in reason.upper()

    def test_lock_in_share_mode(self):
        ok, _ = check("SELECT * FROM sales_data LOCK IN SHARE MODE")
        assert ok is False


# ============================================================
# NHÓM 7: SCHEMA HỆ THỐNG
# ============================================================

class TestSystemSchema:
    """Nhóm test truy cập schema hệ thống"""

    def test_mysql_user(self):
        ok, reason = check("SELECT * FROM mysql.user")
        assert ok is False
        assert "Schema" in reason or "không được phép" in reason

    def test_mysql_db(self):
        ok, _ = check("SELECT * FROM mysql.db")
        assert ok is False

    def test_performance_schema_ok(self):
        """performance_schema được phép (đã có trong whitelist)"""
        # Nếu nhóm chưa cho phép thì có thể đổi thành assert ok is False
        # Hiện tại: chưa có trong ALLOWED_SCHEMAS → sẽ bị chặn
        ok, _ = check("SELECT * FROM performance_schema.events_statements_summary_by_digest")
        assert ok is False  # Từ chối nếu chưa add vào whitelist

    def test_information_schema_ok(self):
        """information_schema được phép"""
        ok, _ = check("SELECT * FROM information_schema.COLUMNS")
        assert ok is True


# ============================================================
# NHÓM 8: PARSE ERROR (FAIL-CLOSED)
# ============================================================

class TestParseError:
    """Nhóm test parse lỗi phải bị chặn (fail-closed)"""

    def test_empty_sql(self):
        ok, reason = check("")
        assert ok is False
        assert "rỗng" in reason.lower()

    def test_whitespace_only(self):
        ok, _ = check("   \t\n  ")
        assert ok is False

    def test_garbage(self):
        ok, _ = check("ABC XYZ 123 !!!")
        assert ok is False

    def test_incomplete_sql(self):
        ok, _ = check("SELECT * FROM")
        assert ok is False


# ============================================================
# CHẠY ĐƠN LẺ ĐỂ XEM OUTPUT
# ============================================================

if __name__ == "__main__":
    import subprocess
    subprocess.run(["pytest", __file__, "-v", "--tb=short"])