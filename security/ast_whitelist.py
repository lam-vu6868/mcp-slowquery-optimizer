"""
security/ast_whitelist.py
-------------------------

CHỨC NĂNG :
    AST whitelist v1 (fail-closed) cho mọi câu SQL nhận từ bên ngoài
    (LLM, slow log, người dùng) TRƯỚC khi Tool 4/5 chạy trên MySQL.

PHỤ TRÁCH  : Tình    |    REVIEW: Vũ (file bảo mật: cần 2 approve)

QUY TẮC (ROADMAP mục 2.2) — mỗi quy tắc có mã `rule` riêng và có test riêng
trong tests/test_ast_whitelist.py:

    not_string          Đầu vào phải là chuỗi.
    empty               Không nhận chuỗi rỗng.
    too_long            Tối đa MAX_SQL_LENGTH ký tự.
    exec_comment        Cấm comment thực thi /*! ... */ và /*M! ... */.
    non_ascii_code      Ký tự ngoài ASCII chỉ được nằm trong chuỗi literal
                        (chặn homoglyph kiểu `ordеrs` dùng chữ "е" Cyrillic).
    multi_statement     Chỉ một statement (cấm dấu ; ngoài chuỗi literal).
    parse_error         Parse lỗi -> từ chối (fail-closed).
    statement_type      Chỉ SELECT (kể cả UNION/INTERSECT/EXCEPT, CTE) và
                        EXPLAIN [FORMAT=TRADITIONAL|JSON|TREE] <SELECT>.
    explain_analyze     Cấm EXPLAIN ANALYZE trong SQL gửi vào. Tool 4 tự thêm
                        ANALYZE sau khi câu SELECT bên trong đã qua whitelist.
    into_clause         Cấm SELECT ... INTO (OUTFILE, DUMPFILE, @biến).
    locking_read        Cấm FOR UPDATE, FOR SHARE, LOCK IN SHARE MODE.
    forbidden_func      Cấm SLEEP, BENCHMARK, GET_LOCK, RELEASE_LOCK, LOAD_FILE,
                        SYS_EXEC... (xem FORBIDDEN_FUNCTIONS).
    variable            Cấm biến hệ thống @@... và biến người dùng @x / @x := ...
    system_schema       Cấm truy cập mysql, information_schema,
                        performance_schema, sys qua SQL tự do.
    schema_not_allowed  Khi truyền allowed_schemas: bảng có tiền tố schema
                        phải thuộc danh sách cho phép.

LƯU Ý:
    - DDL (CREATE INDEX) KHÔNG đi qua đường này: Tool 6 tự sinh DDL từ proposal.
    - Mọi lỗi đều raise SQLRejected (lớp con của ValueError) kèm `rule`, để tool
      trả về mã lỗi AST_REJECTED đúng api-contract.
    - Hai lớp kiểm tra bổ sung cho nhau: (1) quét token (bỏ qua nội dung chuỗi
      literal nên không chặn nhầm 'a;b'), (2) duyệt cây AST của sqlglot.
    - Whitelist chỉ chặn SQL nguy hiểm khi CHẠY. Chỉ thị nhắm vào LLM nằm trong
      comment thường (/* ignore previous instructions */) là việc của sanitize.

THAM KHẢO  : project-management/ROADMAP.md (mục 2.2), docs/api-contract.md (mục 1)
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Set, Tuple

from sqlglot import exp, parse
from sqlglot.dialects.mysql import MySQL
from sqlglot.errors import ParseError, TokenError
from sqlglot.tokens import Token, TokenType

MAX_SQL_LENGTH = 20_000

SYSTEM_SCHEMAS = frozenset({"mysql", "information_schema", "performance_schema", "sys"})

FORBIDDEN_FUNCTIONS = frozenset(
    {
        # treo / làm chậm server
        "sleep",
        "benchmark",
        # khóa cấp ứng dụng
        "get_lock",
        "release_lock",
        "release_all_locks",
        "is_free_lock",
        "is_used_lock",
        # đọc file / chạy lệnh hệ điều hành (UDF hay gặp)
        "load_file",
        "sys_exec",
        "sys_eval",
        # chờ replication -> có thể treo vô hạn
        "master_pos_wait",
        "source_pos_wait",
        "wait_for_executed_gtid_set",
        "wait_until_sql_thread_after_gtids",
    }
)

_STRING_TOKENS = frozenset(
    getattr(TokenType, name)
    for name in (
        "STRING",
        "NATIONAL_STRING",
        "RAW_STRING",
        "HEX_STRING",
        "BIT_STRING",
        "BYTE_STRING",
        "HEREDOC_STRING",
        "UNICODE_STRING",
    )
    if hasattr(TokenType, name)
)

_EXEC_COMMENT_RE = re.compile(r"/\*\s*M?!", re.IGNORECASE)
_EXPLAIN_RE = re.compile(
    r"^\s*(?:EXPLAIN|DESCRIBE|DESC)\b"
    r"(?P<opts>(?:\s+(?:ANALYZE|EXTENDED|PARTITIONS)\b|\s+FORMAT\s*=\s*\w+)*)\s*",
    re.IGNORECASE,
)
_EXPLAIN_FORMAT_RE = re.compile(r"FORMAT\s*=\s*(\w+)", re.IGNORECASE)
_ALLOWED_EXPLAIN_FORMATS = {"traditional", "json", "tree"}

_SELECT_TYPES = (exp.Select, exp.Union, exp.Intersect, exp.Except)
_WRITE_TYPES = (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter, exp.Command)


class SQLRejected(ValueError):
    """SQL bị whitelist từ chối. `rule` là mã quy tắc (xem docstring đầu file)."""

    def __init__(self, rule: str, message: str) -> None:
        super().__init__(f"[{rule}] {message}")
        self.rule = rule
        self.message = message


# ---------------------------------------------------------------------------
# Các bước kiểm tra
# ---------------------------------------------------------------------------


def _normalize(sql: object) -> str:
    if not isinstance(sql, str):
        raise SQLRejected("not_string", "SQL phải là chuỗi.")
    normalized = sql.strip()
    if not normalized:
        raise SQLRejected("empty", "SQL rỗng.")
    if len(normalized) > MAX_SQL_LENGTH:
        raise SQLRejected("too_long", f"SQL dài quá {MAX_SQL_LENGTH} ký tự.")
    return normalized


def _tokenize(sql: str) -> List[Token]:
    try:
        return MySQL().tokenize(sql)
    except (TokenError, ValueError) as exc:
        raise SQLRejected("parse_error", "Không tách token được SQL.") from exc


def _check_tokens(tokens: List[Token]) -> None:
    """Kiểm tra trên token, bỏ qua nội dung chuỗi literal."""

    code_tokens = [t for t in tokens if t.token_type not in _STRING_TOKENS]

    for tok in code_tokens:
        if not tok.text.isascii():
            raise SQLRejected(
                "non_ascii_code",
                f"Ký tự ngoài ASCII trong tên/từ khóa: {tok.text!r} (nghi homoglyph).",
            )

    if any(t.token_type == TokenType.SEMICOLON for t in code_tokens):
        raise SQLRejected("multi_statement", "Chỉ cho phép một statement, không dùng dấu ;.")

    # Ghép lại phần "code" (không có chuỗi literal) để dò cụm từ khóa.
    code = " ".join(t.text.upper() for t in code_tokens)

    if re.search(r"\bINTO\b", code):
        raise SQLRejected("into_clause", "Cấm SELECT ... INTO (OUTFILE/DUMPFILE/biến).")
    if re.search(r"\bFOR\s+(UPDATE|SHARE)\b", code) or re.search(
        r"\bLOCK\s+IN\s+SHARE\s+MODE\b", code
    ):
        raise SQLRejected(
            "locking_read", "Cấm đọc có khóa (FOR UPDATE/FOR SHARE/LOCK IN SHARE MODE)."
        )
    if "@" in code or ":=" in code.replace(" ", ""):
        raise SQLRejected("variable", "Cấm biến hệ thống @@... và biến người dùng @x.")


def _split_explain(sql: str) -> Tuple[bool, str]:
    """Trả (is_explain, phần SQL bên trong)."""

    match = _EXPLAIN_RE.match(sql)
    if not match:
        return False, sql

    opts = match.group("opts") or ""
    if re.search(r"\bANALYZE\b", opts, re.IGNORECASE):
        raise SQLRejected(
            "explain_analyze",
            "Không nhận EXPLAIN ANALYZE từ bên ngoài; Tool 4 tự thêm sau khi kiểm tra.",
        )
    if re.search(r"\b(EXTENDED|PARTITIONS)\b", opts, re.IGNORECASE):
        raise SQLRejected("statement_type", "EXPLAIN EXTENDED/PARTITIONS không được hỗ trợ.")
    fmt = _EXPLAIN_FORMAT_RE.search(opts)
    if fmt and fmt.group(1).lower() not in _ALLOWED_EXPLAIN_FORMATS:
        raise SQLRejected("statement_type", f"EXPLAIN FORMAT={fmt.group(1)} không hợp lệ.")

    inner = sql[match.end():].strip()
    if not inner:
        raise SQLRejected("statement_type", "EXPLAIN thiếu câu SELECT.")
    return True, inner


def _parse_single(sql: str) -> exp.Expression:
    try:
        statements = [s for s in parse(sql, read="mysql") if s is not None]
    except (ParseError, TokenError, ValueError) as exc:
        raise SQLRejected("parse_error", "Không parse được SQL (fail-closed).") from exc
    if len(statements) != 1:
        raise SQLRejected("multi_statement", "Chỉ cho phép đúng một statement.")
    return statements[0]


def _check_tree(tree: exp.Expression, allowed_schemas: Optional[Set[str]]) -> None:
    if not isinstance(tree, _SELECT_TYPES):
        raise SQLRejected(
            "statement_type",
            f"Chỉ cho phép SELECT/EXPLAIN SELECT, nhận được {type(tree).__name__}.",
        )

    for node in tree.walk():
        # Mọi statement con (subquery, CTE, nhánh UNION) cũng phải là SELECT.
        if isinstance(node, _WRITE_TYPES):
            raise SQLRejected(
                "statement_type", f"Phát hiện lệnh {type(node).__name__} bên trong SELECT."
            )
        if isinstance(node, exp.Into):
            raise SQLRejected("into_clause", "Cấm SELECT ... INTO.")
        if isinstance(node, exp.Lock):
            raise SQLRejected("locking_read", "Cấm đọc có khóa.")
        if isinstance(node, (exp.SessionParameter, exp.Parameter)):
            raise SQLRejected("variable", "Cấm biến hệ thống/biến người dùng.")
        if isinstance(node, exp.Func):
            name = (node.name if isinstance(node, exp.Anonymous) else node.sql_name()) or ""
            if name.lower() in FORBIDDEN_FUNCTIONS:
                raise SQLRejected("forbidden_func", f"Cấm hàm {name.upper()}().")

    allowed = {s.lower() for s in allowed_schemas} if allowed_schemas else None
    for table in tree.find_all(exp.Table):
        parts = [p.lower() for p in (table.catalog, table.db, table.name) if p]
        if any(p in SYSTEM_SCHEMAS for p in parts):
            raise SQLRejected("system_schema", "Cấm truy cập schema hệ thống qua SQL tự do.")
        if table.catalog:
            raise SQLRejected(
                "schema_not_allowed", "Tên bảng có quá nhiều cấp (catalog.schema.table)."
            )
        if allowed is not None and table.db and table.db.lower() not in allowed:
            raise SQLRejected(
                "schema_not_allowed",
                f"Schema {table.db!r} không nằm trong danh sách cho phép.",
            )


# ---------------------------------------------------------------------------
# API công khai
# ---------------------------------------------------------------------------


def validate_sql(sql: str, *, allowed_schemas: Optional[Iterable[str]] = None) -> str:
    """Kiểm tra SQL. Hợp lệ -> trả SQL đã strip. Không hợp lệ -> raise SQLRejected."""

    normalized = _normalize(sql)

    if _EXEC_COMMENT_RE.search(normalized):
        raise SQLRejected("exec_comment", "Cấm comment thực thi /*! ... */ hoặc /*M! ... */.")

    _check_tokens(_tokenize(normalized))

    _, inner = _split_explain(normalized)
    tree = _parse_single(inner)
    _check_tree(tree, set(allowed_schemas) if allowed_schemas else None)

    return normalized


def is_allowed_sql(sql: str, *, allowed_schemas: Optional[Iterable[str]] = None) -> bool:
    try:
        validate_sql(sql, allowed_schemas=allowed_schemas)
        return True
    except (TypeError, ValueError):
        return False


def check(sql: str, *, allowed_schemas: Optional[Iterable[str]] = None) -> Dict[str, object]:
    """Dạng dùng trong tool (api-contract mục 1): không raise, trả dict.

    {"ok": True,  "sql": "...", "rule": None, "message": None}
    {"ok": False, "sql": None,  "rule": "multi_statement", "message": "..."}
    """

    try:
        normalized = validate_sql(sql, allowed_schemas=allowed_schemas)
    except SQLRejected as exc:
        return {"ok": False, "sql": None, "rule": exc.rule, "message": exc.message}
    except Exception:  # bất kỳ lỗi lạ nào cũng từ chối (fail-closed)
        return {"ok": False, "sql": None, "rule": "internal", "message": "Lỗi khi kiểm tra SQL."}
    return {"ok": True, "sql": normalized, "rule": None, "message": None}


# Tên cũ, giữ để code khác không vỡ import.
validate_statement = validate_sql
is_safe_sql = is_allowed_sql
allowlist_sql = validate_sql

__all__ = [
    "SQLRejected",
    "FORBIDDEN_FUNCTIONS",
    "SYSTEM_SCHEMAS",
    "MAX_SQL_LENGTH",
    "validate_sql",
    "is_allowed_sql",
    "check",
    "validate_statement",
    "is_safe_sql",
    "allowlist_sql",
]
