"""
mcp_server/store/audit_log.py
-----------------------------
CHỨC NĂNG:
    Ghi nhật ký mọi lần gọi Tool 6 (kể cả bị từ chối) và các thao tác duyệt trên
    Dashboard: thời gian, proposal_id, hash DDL, kết quả, nguồn gọi.

PHỤ TRÁCH: Hải (store) — Tình cài đặt vì Tool 6 phụ thuộc   |   REVIEW: Tình, Hải

LƯU Ý:
    - Chỉ ghi thêm (append-only): trigger SQLite chặn UPDATE/DELETE.
    - KHÔNG BAO GIỜ ghi token vào log (hàm log() không có tham số token).
"""
from datetime import datetime, timezone
from typing import Optional

from mcp_server.store.meta_db import get_meta_conn

# Các action chuẩn, dùng thống nhất giữa Tool 6 và Dashboard
ACTION_APPLY = "apply_optimization"
ACTION_TOKEN_ISSUED = "token_issued"
ACTION_REJECT = "user_reject"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(
    action: str,
    result: str,
    proposal_id: Optional[str] = None,
    ddl_hash: Optional[str] = None,
    error_code: Optional[str] = None,
    message: Optional[str] = None,
    actor: Optional[str] = None,
    source: Optional[str] = None,
) -> str:
    """
    Ghi 1 dòng audit. Trả về audit_id dạng 'a_000123'.

    result: 'success' | 'rejected' | 'error'
    """
    with get_meta_conn() as conn:
        cur = conn.execute(
            """INSERT INTO audit_log
               (ts, action, proposal_id, ddl_hash, result, error_code, message, actor, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                _now_iso(), action, proposal_id, ddl_hash, result, error_code,
                (message or "")[:500], actor, source,
            ),
        )
        return f"a_{cur.lastrowid:06d}"


def list_entries(limit: int = 200, action: Optional[str] = None) -> list[dict]:
    """Đọc audit log mới nhất trước (cho Dashboard tab 4)."""
    sql = "SELECT * FROM audit_log"
    params: list = []
    if action:
        sql += " WHERE action = ?"
        params.append(action)
    sql += " ORDER BY seq DESC LIMIT ?"
    params.append(int(limit))
    with get_meta_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["audit_id"] = f"a_{d.pop('seq'):06d}"
        out.append(d)
    return out


def count_by(error_code: Optional[str] = None, action: Optional[str] = None) -> int:
    sql = "SELECT COUNT(*) FROM audit_log WHERE 1=1"
    params: list = []
    if error_code:
        sql += " AND error_code = ?"
        params.append(error_code)
    if action:
        sql += " AND action = ?"
        params.append(action)
    with get_meta_conn() as conn:
        return int(conn.execute(sql, params).fetchone()[0])
