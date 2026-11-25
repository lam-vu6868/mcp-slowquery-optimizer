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
    - Dùng index_admin cho DDL và SELECT riêng trên mysql.innodb_index_stats để đo index thử.
    - Helper DDL nội bộ trong file này phục vụ Validation tạo/dọn index INVISIBLE; không công bố thành MCP tool.
    - Từ chối index thử có tiền tố trùng cột FK tham chiếu để tránh MySQL tự bỏ index hỗ trợ FK.
    - Recovery không DROP trial nếu nó là index duy nhất còn hỗ trợ FK tham chiếu.
    - Chụp metadata FK/index bằng tài khoản đọc trước khi backend ghi trial pending và tạo index.
    - Recovery chỉ khôi phục một index FK đơn giản từ snapshot đã lưu, xác minh lại rồi mới dọn trial.
    - Mọi lần gọi (kể cả bị từ chối) đều ghi audit_log.

THAM KHẢO  : docs/api-contract.md (Tool 6), security/approval.py

TRẠNG THÁI : ĐANG LÀM — đã có helper index thử nội bộ; Tool 6 chưa cài đặt.
"""

import re
import uuid

import pymysql

from mcp_server.utils.config import Config
from mcp_server.utils.db import get_admin_conn, get_conn

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_INDEX_NAME = re.compile(r"^idx_[a-z0-9_]{1,50}$")
_PROPOSAL_ID = re.compile(r"^p_[a-z0-9_]{1,64}$")


class ForeignKeyIndexRisk(ValueError):
    """Index mới có thể thay thế index mà khóa ngoại đang dùng."""


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
        self._baseline_allocated_size = None

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

    def _tablespace_allocated_size(self) -> int | None:
        """Dung lượng file riêng của bảng; không suy ra byte chính xác từng index."""
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT SPACE_TYPE, ALLOCATED_SIZE "
                "FROM information_schema.INNODB_TABLESPACES WHERE NAME=%s",
                (f"{Config.DB_NAME}/{self.table_name}",),
            )
            row = cur.fetchone()
        if row is None or row["SPACE_TYPE"] != "Single":
            return None
        return None if row["ALLOCATED_SIZE"] is None else int(row["ALLOCATED_SIZE"])

    def _index_stats_size(self) -> int | None:
        """Số trang của đúng index thử; thiếu quyền SELECT thì dùng nguồn dự phòng."""
        try:
            with get_admin_conn() as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT stat_value, @@innodb_page_size AS page_size "
                    "FROM mysql.innodb_index_stats "
                    "WHERE database_name=%s AND table_name=%s "
                    "AND index_name=%s AND stat_name='size'",
                    (Config.DB_NAME, self.table_name, self.index_name),
                )
                row = cur.fetchone()
        except pymysql.err.OperationalError as exc:
            if exc.args[0] == 1142:  # SELECT chưa được cấp trên bảng stats
                return None
            raise
        if row is None or row["stat_value"] is None or row["page_size"] is None:
            return None
        pages, page_size = int(row["stat_value"]), int(row["page_size"])
        return pages * page_size if pages > 0 and page_size > 0 else None

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
            cur.execute(
                "SELECT CONSTRAINT_NAME, COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s "
                "AND REFERENCED_TABLE_NAME IS NOT NULL "
                "ORDER BY CONSTRAINT_NAME, ORDINAL_POSITION",
                (Config.DB_NAME, self.table_name),
            )
            foreign_keys = {}
            for row in cur.fetchall():
                foreign_keys.setdefault(row["CONSTRAINT_NAME"], []).append(row["COLUMN_NAME"])
        if not known or any(name not in known for name in self.column_names):
            raise ValueError("table/column không tồn tại trong schema")
        if self.index_name in existing:
            raise ValueError("index_name đã tồn tại")
        if any(self.column_names == cols[:len(self.column_names)]
               for cols in existing.values()):
            raise ValueError("columns là tiền tố thừa của index hiện có")
        if any(self.column_names[:len(cols)] == cols for cols in foreign_keys.values()):
            raise ForeignKeyIndexRisk("index đề xuất có thể thay thế index hỗ trợ khóa ngoại")

    def fk_support_snapshot(self) -> dict:
        """Chụp FK và định nghĩa index hỗ trợ bằng tài khoản đọc, trước mọi DDL."""
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT CONSTRAINT_NAME, COLUMN_NAME "
                "FROM information_schema.KEY_COLUMN_USAGE "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s "
                "AND REFERENCED_TABLE_NAME IS NOT NULL "
                "ORDER BY CONSTRAINT_NAME, ORDINAL_POSITION",
                (Config.DB_NAME, self.table_name),
            )
            foreign_keys = {}
            for row in cur.fetchall():
                foreign_keys.setdefault(row["CONSTRAINT_NAME"], []).append(row["COLUMN_NAME"])
            if not foreign_keys:
                return {"foreign_keys": [], "supporting_indexes": []}
            cur.execute(
                "SELECT INDEX_NAME, COLUMN_NAME, COLLATION, SUB_PART, NON_UNIQUE, "
                "INDEX_TYPE, IS_VISIBLE, INDEX_COMMENT "
                "FROM information_schema.STATISTICS "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s "
                "ORDER BY INDEX_NAME, SEQ_IN_INDEX",
                (Config.DB_NAME, self.table_name),
            )
            indexes = {}
            for row in cur.fetchall():
                indexes.setdefault(row["INDEX_NAME"], []).append(row)
        support = []
        for name, rows in indexes.items():
            columns = [row["COLUMN_NAME"] for row in rows]
            if not any(columns[:len(fk_cols)] == fk_cols
                       for fk_cols in foreign_keys.values()):
                continue
            support.append({
                "name": name, "non_unique": int(rows[0]["NON_UNIQUE"]),
                "index_type": rows[0]["INDEX_TYPE"],
                "visible": rows[0]["IS_VISIBLE"] == "YES",
                "comment": rows[0]["INDEX_COMMENT"],
                "columns": [{
                    "name": row["COLUMN_NAME"],
                    "order": ({"A": "ASC", "D": "DESC"}.get(row["COLLATION"])),
                    "sub_part": row["SUB_PART"],
                } for row in rows],
            })
        if any(not any([row["name"] for row in index["columns"]][:len(fk_cols)]
                       == fk_cols for index in support)
               for fk_cols in foreign_keys.values()):
            raise ForeignKeyIndexRisk("không đọc được index hỗ trợ khóa ngoại")
        return {
            "foreign_keys": [{"name": name, "columns": columns}
                             for name, columns in foreign_keys.items()],
            "supporting_indexes": support,
        }

    def create(self) -> None:
        self._check_schema()
        self._baseline_size = self._index_length()
        self._baseline_allocated_size = self._tablespace_allocated_size()
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

    def size_delta(self) -> dict:
        if not self._owned or self._index_state() != "owned":
            return {"index_size_bytes": None, "index_size_source": None}
        stats_size = self._index_stats_size()
        if stats_size is not None:
            return {"index_size_bytes": stats_size,
                    "index_size_source": "innodb_index_stats_pages"}
        after = self._index_length()
        if after is not None and self._baseline_size is not None:
            delta = after - self._baseline_size
            if delta > 0:
                return {"index_size_bytes": delta,
                        "index_size_source": "table_index_length_delta"}
        allocated_after = self._tablespace_allocated_size()
        if allocated_after is not None and self._baseline_allocated_size is not None:
            delta = allocated_after - self._baseline_allocated_size
            if delta > 0:
                return {"index_size_bytes": delta,
                        "index_size_source": "tablespace_allocated_growth_delta"}
        return {"index_size_bytes": None, "index_size_source": None}

    def drop(self) -> None:
        if not self._attempted_create and not self._owned:
            return
        self.recover_drop()
        self._owned = False
        self._attempted_create = False

    def _sole_fk_support(self) -> bool:
        """Kiểm tra liệu bỏ trial có làm FK phía tham chiếu mất index hỗ trợ."""
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT CONSTRAINT_NAME, COLUMN_NAME "
                "FROM information_schema.KEY_COLUMN_USAGE "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s "
                "AND REFERENCED_TABLE_NAME IS NOT NULL "
                "ORDER BY CONSTRAINT_NAME, ORDINAL_POSITION",
                (Config.DB_NAME, self.table_name),
            )
            foreign_keys = {}
            for row in cur.fetchall():
                foreign_keys.setdefault(row["CONSTRAINT_NAME"], []).append(row["COLUMN_NAME"])
            if not foreign_keys:
                return False
            cur.execute(
                "SELECT INDEX_NAME, COLUMN_NAME FROM information_schema.STATISTICS "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s "
                "ORDER BY INDEX_NAME, SEQ_IN_INDEX",
                (Config.DB_NAME, self.table_name),
            )
            indexes = {}
            for row in cur.fetchall():
                indexes.setdefault(row["INDEX_NAME"], []).append(row["COLUMN_NAME"])
        return any(
            not any(name != self.index_name and cols[:len(fk_cols)] == fk_cols
                    for name, cols in indexes.items())
            for fk_cols in foreign_keys.values()
        )

    def restore_fk_support(self, snapshot: dict) -> str:
        """Chỉ dựng lại một index FK đơn giản đã lưu trước DDL, rồi xác minh metadata."""
        state = self._index_state()
        if not isinstance(snapshot, dict):
            raise ForeignKeyIndexRisk("thiếu snapshot FK")
        current = self.fk_support_snapshot()
        if state == "absent":
            if current == snapshot:
                return "absent"
            raise ForeignKeyIndexRisk("trial chưa có nhưng schema FK đã đổi")
        if state != "owned":
            raise ForeignKeyIndexRisk("trial không thuộc proposal")
        if current["foreign_keys"] != snapshot.get("foreign_keys"):
            raise ForeignKeyIndexRisk("FK đã đổi từ lúc tạo trial")
        saved_indexes = {item["name"]: item for item in snapshot["supporting_indexes"]}
        live_indexes = {item["name"]: item for item in current["supporting_indexes"]}
        if (self.index_name in saved_indexes
                or set(live_indexes) - set(saved_indexes) - {self.index_name}
                or any(live_indexes[name] != index
                       for name, index in saved_indexes.items() if name in live_indexes)):
            raise ForeignKeyIndexRisk("index hỗ trợ FK đã đổi")
        missing = [index for name, index in saved_indexes.items() if name not in live_indexes]
        if not missing:
            return "present"
        if len(missing) != 1:
            raise ForeignKeyIndexRisk("nhiều index hỗ trợ FK bị thiếu")
        index = missing[0]
        columns = index["columns"]
        original_columns = [col["name"] for col in columns]
        affected_fks = [fk["columns"] for fk in snapshot["foreign_keys"]
                        if original_columns[:len(fk["columns"])] == fk["columns"]]
        if not affected_fks:
            raise ForeignKeyIndexRisk("index trong snapshot không hỗ trợ FK")
        trial_index = live_indexes.get(self.index_name)
        if (trial_index is None or any(
            [col["name"] for col in trial_index["columns"]][:len(fk_cols)] != fk_cols
            for fk_cols in affected_fks
        )):
            raise ForeignKeyIndexRisk("index bị thiếu không do trial hỗ trợ FK đó")
        if (index["non_unique"] != 1 or index["index_type"] != "BTREE"
                or index["visible"] is not True or index["comment"] != ""
                or not columns or any(col["order"] != "ASC" or col["sub_part"] is not None
                                       for col in columns)):
            raise ForeignKeyIndexRisk("không thể khôi phục an toàn định nghĩa index FK")
        try:
            name = _quote_identifier(index["name"])
            column_sql = ", ".join(_quote_identifier(col["name"]) for col in columns)
        except ValueError as exc:
            raise ForeignKeyIndexRisk("tên index hoặc cột FK không hợp lệ") from exc
        ddl = f"CREATE INDEX {name} ON {self.table} ({column_sql}) VISIBLE"
        with get_admin_conn() as conn, conn.cursor() as cur:
            cur.execute("SET SESSION lock_wait_timeout = 5")
            cur.execute(ddl)
        after = self.fk_support_snapshot()
        restored = {item["name"]: item for item in after["supporting_indexes"]}
        if (after["foreign_keys"] != snapshot["foreign_keys"]
                or restored.get(index["name"]) != index
                or self._index_state() != "owned"):
            raise ForeignKeyIndexRisk("không xác minh được index FK sau khôi phục")
        return "restored"

    def recover_drop(self) -> str:
        """Dọn sau restart, chỉ khi marker/định nghĩa/INVISIBLE đều khớp."""
        state = self._index_state()
        if state == "absent":
            return "absent"
        if self._sole_fk_support():
            raise ForeignKeyIndexRisk("index thử là index duy nhất hỗ trợ khóa ngoại")
        with get_admin_conn() as conn, conn.cursor() as cur:
            cur.execute("SET SESSION lock_wait_timeout = 5")
            cur.execute(self.drop_ddl)
        self._owned = False
        return "dropped"
