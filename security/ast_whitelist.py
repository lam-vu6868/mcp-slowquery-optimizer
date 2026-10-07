"""
security/ast_whitelist.py
-------------------------
CHỨC NĂNG:
    Parse SQL qua sqlglot, chặn mọi câu lệnh nguy hiểm.
    Chỉ cho phép: SELECT, EXPLAIN, và CREATE INDEX (do server sinh).

PHỤ TRÁCH: Tình    |    REVIEW: Vũ
THAM KHẢO: project-management/ROADMAP.md mục 2.2

QUY TẮC (theo ROADMAP):
    1. Chỉ 1 statement (chặn `;` nối lệnh)
    2. Chỉ cho SELECT, EXPLAIN (không EXPLAIN ANALYZE từ LLM)
    3. Từ chối comment thực thi /*! ... */ và /*M! ... */
    4. Từ chối INTO OUTFILE, INTO DUMPFILE, LOAD_FILE(), FOR UPDATE, LOCK IN SHARE MODE
    5. Từ chối hàm nguy hiểm: SLEEP, BENCHMARK, GET_LOCK, RELEASE_LOCK, SYS_EXEC
    6. Từ chối truy cập schema hệ thống (mysql.*, information_schema.* tự do)
    7. DDL duy nhất được phép: CREATE INDEX (server sinh, không qua LLM)
    8. Parse lỗi → TỪ CHỐI (fail-closed)
"""
"""
security/ast_whitelist.py
-------------------------
CHỨC NĂNG:
    Parse SQL qua sqlglot, chặn mọi câu lệnh nguy hiểm.
    Chỉ cho phép: SELECT, EXPLAIN, và CREATE INDEX (do server sinh).

PHỤ TRÁCH: Tình    |    REVIEW: Vũ
THAM KHẢO: project-management/ROADMAP.md mục 2.2
"""
import re
from typing import Tuple

try:
    import sqlglot
    from sqlglot import exp
    SQLGLOT_AVAILABLE = True
except ImportError:
    SQLGLOT_AVAILABLE = False


# ============================================================
# CẤU HÌNH
# ============================================================

ALLOWED_ROOTS = None  # set sau

FORBIDDEN_KEYWORDS = [
    "INTO OUTFILE",
    "INTO DUMPFILE",
    "LOAD_FILE",
    "SLEEP",
    "BENCHMARK",
    "GET_LOCK",
    "RELEASE_LOCK",
    "SYS_EXEC",
    "SYSTEM_USER",
    "FOR UPDATE",
    "LOCK IN SHARE MODE",
]

FORBIDDEN_FUNCTIONS = {
    "sleep", "benchmark", "get_lock", "release_lock",
    "sys_exec", "load_file", "system_user",
}

ALLOWED_SCHEMAS = {"shopdb", "information_schema"}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _init_allowed_roots():
    """Set ALLOWED_ROOTS sau khi import exp thành công"""
    global ALLOWED_ROOTS
    if SQLGLOT_AVAILABLE:
        roots = [exp.Select, exp.Union, exp.Except, exp.Intersect]
        ALLOWED_ROOTS = tuple(roots)
    else:
        ALLOWED_ROOTS = ()


def _contains_executable_comment(sql: str) -> bool:
    """Chặn /*! ... */ và /*M! ... */ (MySQL executable comments)"""
    return "/*!" in sql or "/*M!" in sql or "/*m!" in sql


def _has_multi_statement(sql: str) -> bool:
    """Chặn `;` nối nhiều statement"""
    stripped = sql.strip()
    if stripped.endswith(";"):
        stripped = stripped[:-1]
    return ";" in stripped


def _has_forbidden_keyword(sql: str) -> Tuple[bool, str]:
    """Check keyword nguy hiểm bằng text search"""
    sql_upper = sql.upper()
    for kw in FORBIDDEN_KEYWORDS:
        if kw in sql_upper:
            return True, f"Keyword bị chặn: {kw}"
    return False, ""


def _has_forbidden_function(parsed) -> Tuple[bool, str]:
    """Check hàm nguy hiểm bằng AST walk"""
    for node in parsed.walk():
        if isinstance(node, exp.Anonymous):
            func_name = (node.this or "").lower()
            if func_name in FORBIDDEN_FUNCTIONS:
                return True, f"Hàm bị chặn: {func_name}()"
        func_class = type(node).__name__.lower()
        if func_class in FORBIDDEN_FUNCTIONS:
            return True, f"Hàm bị chặn: {func_class}()"
    return False, ""


def _check_table_schemas(parsed) -> Tuple[bool, str]:
    """Chặn truy cập schema ngoài whitelist"""
    for table in parsed.find_all(exp.Table):
        db = table.db
        if db and db.lower() not in ALLOWED_SCHEMAS:
            return False, f"Schema không được phép: {db}"
    return True, ""


def _is_create_index(parsed) -> bool:
    """Check có phải CREATE INDEX không"""
    if not isinstance(parsed, exp.Create):
        return False
    kind = (parsed.args.get("kind") or "").upper()
    return kind == "INDEX"


def _extract_inner_sql_from_explain(sql: str) -> str:
    """
    Trích phần SQL bên trong EXPLAIN.
    Ví dụ:
        "EXPLAIN SELECT * FROM t" → "SELECT * FROM t"
        "EXPLAIN FORMAT=JSON SELECT * FROM t" → "SELECT * FROM t"
    """
    s = re.sub(r'^\s*EXPLAIN\s+', '', sql, flags=re.IGNORECASE)
    s = re.sub(r'^FORMAT\s*=\s*\w+\s+', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^ANALYZE\s+', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^EXTENDED\s+', '', s, flags=re.IGNORECASE)
    return s.strip()


# ============================================================
# MAIN FUNCTION
# ============================================================

def check(sql: str) -> Tuple[bool, str]:
    """
    Kiểm tra SQL có an toàn không.

    Returns:
        (True, "OK") nếu an toàn
        (False, "lý do") nếu bị chặn
    """
    if not sql or not sql.strip():
        return False, "SQL rỗng"

    if not SQLGLOT_AVAILABLE:
        return False, "sqlglot chưa cài đặt (pip install sqlglot)"

    sql = sql.strip()

    # ---- LỚP 1: Check text nhanh ----
    if _contains_executable_comment(sql):
        return False, "Executable comment bị chặn (/*! ... */ hoặc /*M! ... */)"

    if _has_multi_statement(sql):
        return False, "Multi-statement không được phép"

    has_kw, reason = _has_forbidden_keyword(sql)
    if has_kw:
        return False, reason

    # ---- LỚP 2: Xử lý EXPLAIN đặc biệt ----
    sql_upper = sql.upper().lstrip()
    if sql_upper.startswith("EXPLAIN"):
        inner_sql = _extract_inner_sql_from_explain(sql)
        if not inner_sql:
            return False, "EXPLAIN không có câu lệnh bên trong"
        try:
            inner_parsed = sqlglot.parse_one(inner_sql, dialect="mysql")
            if inner_parsed is None or not isinstance(inner_parsed, ALLOWED_ROOTS):
                return False, f"EXPLAIN chỉ cho phép SELECT"
            has_func, reason = _has_forbidden_function(inner_parsed)
            if has_func:
                return False, reason
            ok, reason = _check_table_schemas(inner_parsed)
            if not ok:
                return False, reason
            return True, "OK"
        except Exception as e:
            return False, f"EXPLAIN parse error: {str(e)[:100]}"

    # ---- LỚP 3: Parse AST ----
    try:
        parsed = sqlglot.parse_one(sql, dialect="mysql")
    except Exception as e:
        return False, f"Parse error: {str(e)[:100]}"

    if parsed is None:
        return False, "Parse trả về None"

    # ---- LỚP 4: Check root type ----
    is_create_idx = _is_create_index(parsed)

    if not isinstance(parsed, ALLOWED_ROOTS) and not is_create_idx:
        return False, f"Loại câu lệnh không được phép: {type(parsed).__name__}"

    # ---- LỚP 5: Check hàm nguy hiểm ----
    has_func, reason = _has_forbidden_function(parsed)
    if has_func:
        return False, reason

    # ---- LỚP 6: Check schema ----
    ok, reason = _check_table_schemas(parsed)
    if not ok:
        return False, reason

    return True, "OK"


# ============================================================
# DEBUG
# ============================================================

def explain_reject(sql: str) -> str:
    """Trả về lý do từ chối rõ ràng"""
    ok, reason = check(sql)
    if ok:
        return "✅ ALLOWED"
    return f"❌ REJECTED: {reason}"


# Init
_init_allowed_roots()


# ============================================================
# CHẠY TRỰC TIẾP
# ============================================================

if __name__ == "__main__":
    samples = [
        ("SELECT * FROM sales_data WHERE region='Asia'", True),
        ("EXPLAIN SELECT * FROM sales_data", True),
        ("EXPLAIN FORMAT=JSON SELECT * FROM sales_data", True),
        ("SELECT COUNT(*) FROM sales_data", True),
        ("CREATE INDEX idx_x ON sales_data(region)", True),
        ("DROP TABLE sales_data", False),
        ("DELETE FROM sales_data", False),
        ("UPDATE sales_data SET region='X'", False),
        ("INSERT INTO sales_data VALUES (1,2,3)", False),
        ("TRUNCATE TABLE sales_data", False),
        ("SELECT 1; DROP TABLE sales_data", False),
        ("SELECT * FROM sales_data INTO OUTFILE '/tmp/x'", False),
        ("SELECT SLEEP(10)", False),
        ("SELECT BENCHMARK(1000000, MD5('x'))", False),
        ("/*!50000 DROP TABLE sales_data */", False),
        ("SELECT * FROM mysql.user", False),
        ("SELECT * FROM sales_data FOR UPDATE", False),
        ("", False),
        ("ABC XYZ", False),
    ]

    print("=" * 70)
    print("🧪 TEST AST WHITELIST — QUICK CHECK")
    print("=" * 70)

    passed = 0
    for sql, expected in samples:
        ok, reason = check(sql)
        status = "✅" if ok == expected else "❌"
        if ok == expected:
            passed += 1
        print(f"{status} | {'ALLOW' if ok else 'BLOCK':5} | {sql[:55]:55} | {reason[:40]}")

    print("=" * 70)
    print(f"Kết quả: {passed}/{len(samples)} pass")
    print("=" * 70)