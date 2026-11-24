"""
mcp_server/tools/apply.py
-------------------------

CHỨC NĂNG :
    TOOL 6 — apply_optimization: áp dụng THẬT một đề xuất index đã được người duyệt.

PHỤ TRÁCH  : Tình    |    REVIEW: Vũ + Hải (BẮT BUỘC cả hai)

LƯU Ý:
    - KHÔNG được cấp cho LLM. Chỉ backend Dashboard gọi.
    - Input CHỈ gồm proposal_id + approval_token. TUYỆT ĐỐI không nhận SQL tự do.
    - Kiểm token: đúng chữ ký, chưa hết hạn, chưa dùng, khớp proposal ID/version và hash DDL ALTER INDEX VISIBLE thực tế.
    - Proposal loại 'rewrite' luôn bị từ chối (FORBIDDEN).
    - Chỉ cho apply khi validation_report.status == 'passed' và đủ bằng chứng đo.
    - Dùng tài khoản index_admin (chỉ CREATE/DROP INDEX, ALTER INDEX).
    - Helper DDL nội bộ trong file này phục vụ Validation tạo/dọn index INVISIBLE; không công bố thành MCP tool.
    - Mọi lần gọi (kể cả bị từ chối) đều ghi audit_log.

THAM KHẢO  : docs/api-contract.md (Tool 6), security/approval.py

TRẠNG THÁI : ĐANG LÀM — đã có helper index thử nội bộ; Tool 6 chưa cài đặt.
"""

import re
import uuid

from mcp_server.utils.config import Config
from mcp_server.utils.db import get_admin_conn, get_conn

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_INDEX_NAME = re.compile(r"^idx_[a-z0-9_]{1,50}$")
_PROPOSAL_ID = re.compile(r"^p_[a-z0-9_]{1,64}$")


def _quote_identifier(value: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError("identifier không hợp lệ")
    return f"`{value}`"


class TrialIndex:
    """Chỉ quản lý index thử do instance này tạo; không nhận DDL từ caller."""

    def __init__(self, proposal: dict, *, proposal_id: str | None = None):
        if not isinstance(proposal, dict) or proposal.get("type") != "index":
            raise ValueError("chỉ nhận IndexProposal")
        table = proposal.get("table")
        name = proposal.get("index_name")
        columns = proposal.get("columns")
        self.table = _quote_identifier(table)
        if not isinstance(name, str) or not _INDEX_NAME.fullmatch(name):
            raise ValueError("index_name không hợp lệ")
        self.name = _quote_identifier(name)
        if not isinstance(columns, list) or not 1 <= len(columns) <= 5:
            raise ValueError("columns phải có 1–5 cột")
        column_sql = []
        self.column_names = []
        self.column_parts = []
        for column in columns:
            if not isinstance(column, dict) or column.get("order") not in ("ASC", "DESC"):
                raise ValueError("column order không hợp lệ")
            col_name = column.get("name")
            column_sql.append(f"{_quote_identifier(col_name)} {column['order']}")
            self.column_names.append(col_name)
            self.column_parts.append((col_name, column["order"]))
        self.table_name = table
        self.index_name = name
        self.proposal_id = proposal_id or f"p_{uuid.uuid4().hex}"
        if not _PROPOSAL_ID.fullmatch(self.proposal_id):
            raise ValueError("proposal_id không hợp lệ")
        self.marker = f"mcp_trial:{self.proposal_id}"
        self.create_ddl = (
            f"CREATE INDEX {self.name} ON {self.table} "
            f"({', '.join(column_sql)}) COMMENT '{self.marker}' INVISIBLE"
        )
        self.drop_ddl = f"DROP INDEX {self.name} ON {self.table}"
        self._owned = False
        self._attempted_create = False
        self._baseline_size = None

    def _index_length(self) -> int | None:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SET SESSION information_schema_stats_expiry = 0")
            cur.execute(
                "SELECT INDEX_LENGTH FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
                (Config.DB_NAME, self.table_name),
            )
            row = cur.fetchone()
        return None if row is None or row["INDEX_LENGTH"] is None else int(row["INDEX_LENGTH"])

    def _check_schema(self) -> None:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
                (Config.DB_NAME, self.table_name),
            )
            known = {row["COLUMN_NAME"] for row in cur.fetchall()}
            cur.execute(
                "SELECT INDEX_NAME, COLUMN_NAME, SEQ_IN_INDEX "
                "FROM information_schema.STATISTICS "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s "
                "ORDER BY INDEX_NAME, SEQ_IN_INDEX",
                (Config.DB_NAME, self.table_name),
            )
            existing = {}
            for row in cur.fetchall():
                existing.setdefault(row["INDEX_NAME"], []).append(row["COLUMN_NAME"])
        if not known or any(name not in known for name in self.column_names):
            raise ValueError("table/column không tồn tại trong schema")
        if self.index_name in existing:
            raise ValueError("index_name đã tồn tại")
        if any(self.column_names == cols[:len(self.column_names)]
               for cols in existing.values()):
            raise ValueError("columns là tiền tố thừa của index hiện có")

    def create(self) -> None:
        self._check_schema()
        self._baseline_size = self._index_length()
        with get_admin_conn() as conn, conn.cursor() as cur:
            cur.execute("SET SESSION lock_wait_timeout = 5")
            self._attempted_create = True
            cur.execute(self.create_ddl)
            self._owned = True
        if self._index_state() != "owned":
            raise RuntimeError("index thử chưa được xác nhận INVISIBLE/cùng proposal")

    def _index_state(self) -> str:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT COLUMN_NAME, COLLATION, INDEX_COMMENT, IS_VISIBLE "
                "FROM information_schema.STATISTICS "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND INDEX_NAME=%s "
                "ORDER BY SEQ_IN_INDEX",
                (Config.DB_NAME, self.table_name, self.index_name),
            )
            rows = cur.fetchall()
        if not rows:
            return "absent"
        columns = [(row["COLUMN_NAME"], row["COLLATION"]) for row in rows]
        expected = [(column, "A" if direction == "ASC" else "D")
                    for column, direction in self.column_parts]
        if (columns != expected or any(
            row["INDEX_COMMENT"] != self.marker or row["IS_VISIBLE"] != "NO"
            for row in rows
        )):
            raise RuntimeError("index không thuộc trial này hoặc đã đổi định nghĩa")
        return "owned"

    def size_delta(self) -> int | None:
        if not self._owned or self._baseline_size is None:
            return None
        after = self._index_length()
        return None if after is None else max(0, after - self._baseline_size)

    def drop(self) -> None:
        if not self._attempted_create and not self._owned:
            return
        self.recover_drop()
        self._owned = False
        self._attempted_create = False

    def recover_drop(self) -> str:
        """Dọn sau restart, chỉ khi marker/định nghĩa/INVISIBLE đều khớp."""
        state = self._index_state()
        if state == "absent":
            return "absent"
        with get_admin_conn() as conn, conn.cursor() as cur:
            cur.execute("SET SESSION lock_wait_timeout = 5")
            cur.execute(self.drop_ddl)
        self._owned = False
        return "dropped"
