"""
mcp_server/store/audit_log.py
-----------------------------

CHỨC NĂNG :
    Ghi nhật ký mọi lần gọi Tool 6 (kể cả bị từ chối): thời gian, proposal_id, hash DDL, kết quả.

PHỤ TRÁCH  : Hải    |    REVIEW: Tình

LƯU Ý:
    - Chỉ ghi thêm (append-only), không sửa/xóa.
    - Không ghi token vào log.

TRẠNG THÁI : ĐANG LÀM — đã lưu bản ghi audit; Tool 6 chưa nối.
"""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path


class AuditLog:
    """Lưu sự kiện Tool 6 vào SQLite riêng; API chỉ hỗ trợ ghi thêm."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    proposal_id TEXT,
                    ddl_sha256 TEXT,
                    result TEXT NOT NULL,
                    approver TEXT NOT NULL,
                    source TEXT NOT NULL,
                    reason TEXT
                )
            """)
            conn.commit()

    def append(self, *, proposal_id: str | None, ddl_sha256: str | None,
               result: str, approver: str, source: str,
               reason: str | None) -> int:
        with closing(sqlite3.connect(self.path)) as conn:
            cur = conn.execute(
                "INSERT INTO audit_log "
                "(created_at, proposal_id, ddl_sha256, result, approver, source, reason) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (datetime.now(UTC).isoformat(), proposal_id, ddl_sha256,
                 result, approver, source, reason),
            )
            conn.commit()
            return cur.lastrowid
