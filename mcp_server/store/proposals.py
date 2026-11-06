"""
mcp_server/store/proposals.py
-----------------------------
CHỨC NĂNG:
    Lưu và truy xuất đề xuất (proposal) của LLM cùng validation_report.

PHỤ TRÁCH: Hải — Tình cài đặt bản tối thiểu vì Tool 6 + Dashboard phụ thuộc  |  REVIEW: Hải, Vũ

LƯU Ý:
    - Lưu trong SQLite meta (mcp_server/store/meta_db.py), TÁCH khỏi shopdb.
    - Vòng đời trạng thái:
        pending_validation ─▶ validated ─▶ applied
                      │            ├────▶ rejected_by_user
                      │            └────▶ apply_failed
                      └─▶ rejected_by_validation
      Proposal 'rewrite' chỉ để hiển thị: trạng thái tối đa là 'validated'.
"""
import json
import secrets
from datetime import datetime, timezone
from typing import Optional

from mcp_server.store.meta_db import get_meta_conn

STATUS_PENDING = "pending_validation"
STATUS_VALIDATED = "validated"
STATUS_REJECTED_BY_VALIDATION = "rejected_by_validation"
STATUS_REJECTED_BY_USER = "rejected_by_user"
STATUS_APPLIED = "applied"
STATUS_APPLY_FAILED = "apply_failed"

ALL_STATUSES = {
    STATUS_PENDING, STATUS_VALIDATED, STATUS_REJECTED_BY_VALIDATION,
    STATUS_REJECTED_BY_USER, STATUS_APPLIED, STATUS_APPLY_FAILED,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_proposal_id() -> str:
    return f"p_{datetime.now(timezone.utc):%Y%m%d}_{secrets.token_hex(3)}"


def save_proposal(
    payload: dict,
    query_id: Optional[str] = None,
    proposal_id: Optional[str] = None,
    source: str = "llm",
) -> str:
    """Lưu proposal mới (trạng thái pending_validation). Trả về proposal_id."""
    ptype = payload.get("type")
    if ptype not in ("index", "rewrite"):
        raise ValueError(f"type không hợp lệ: {ptype!r}")
    pid = proposal_id or new_proposal_id()
    now = _now_iso()
    qid = query_id or payload.get("original_query_id") or (
        (payload.get("target_query_ids") or [None])[0]
    )
    with get_meta_conn() as conn:
        conn.execute(
            """INSERT INTO proposals
               (proposal_id, query_id, type, payload_json, status, source, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (pid, qid, ptype, json.dumps(payload, ensure_ascii=False),
             STATUS_PENDING, source, now, now),
        )
    return pid


def _row_to_dict(row) -> dict:
    d = dict(row)
    d["payload"] = json.loads(d.pop("payload_json"))
    return d


def get_proposal(proposal_id: str) -> Optional[dict]:
    with get_meta_conn() as conn:
        row = conn.execute(
            "SELECT * FROM proposals WHERE proposal_id = ?", (proposal_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_proposals(status: Optional[str] = None, limit: int = 100) -> list[dict]:
    sql = "SELECT * FROM proposals"
    params: list = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(int(limit))
    with get_meta_conn() as conn:
        return [_row_to_dict(r) for r in conn.execute(sql, params).fetchall()]


def set_status(proposal_id: str, status: str) -> None:
    if status not in ALL_STATUSES:
        raise ValueError(f"status không hợp lệ: {status!r}")
    with get_meta_conn() as conn:
        conn.execute(
            "UPDATE proposals SET status = ?, updated_at = ? WHERE proposal_id = ?",
            (status, _now_iso(), proposal_id),
        )


def save_validation_report(proposal_id: str, report: dict) -> None:
    """
    Lưu validation_report (định dạng api-contract mục 4) và cập nhật trạng thái proposal.
    Validation Layer (Hải) gọi hàm này sau khi đo xong.
    """
    status = report.get("status")
    if status not in ("passed", "failed"):
        raise ValueError("report.status phải là 'passed' hoặc 'failed'")
    with get_meta_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO validation_reports
               (proposal_id, status, report_json, created_at) VALUES (?, ?, ?, ?)""",
            (proposal_id, status, json.dumps(report, ensure_ascii=False), _now_iso()),
        )
    set_status(
        proposal_id,
        STATUS_VALIDATED if status == "passed" else STATUS_REJECTED_BY_VALIDATION,
    )


def get_validation_report(proposal_id: str) -> Optional[dict]:
    with get_meta_conn() as conn:
        row = conn.execute(
            "SELECT report_json FROM validation_reports WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
    return json.loads(row[0]) if row else None
