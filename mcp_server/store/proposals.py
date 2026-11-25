"""
mcp_server/store/proposals.py
-----------------------------

CHỨC NĂNG :
    Lưu và truy xuất đề xuất (proposal) cùng validation_report.

PHỤ TRÁCH  : Hải    |    REVIEW: Vũ

LƯU Ý:
    - Dùng SQLite riêng hoặc schema optimizer_meta, TÁCH khỏi schema thực nghiệm mà LLM/readonly_user đọc được.

THAM KHẢO  : docs/api-contract.md

TRẠNG THÁI : ĐANG LÀM — lưu proposal/report bất biến trong SQLite riêng; chưa nối Dashboard.
"""

import json
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

from mcp_server.tools.apply import TrialIndex
from mcp_server.validation.validator import assess_index_report
from security.ast_whitelist import check as ast_check


class ProposalStore:
    """Lưu metadata ngoài shopdb; caller chọn đường dẫn SQLite không nằm trong Git."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS proposals (
                    proposal_id TEXT PRIMARY KEY,
                    query_id TEXT NOT NULL,
                    original_sql TEXT NOT NULL,
                    proposal_json TEXT NOT NULL,
                    report_json TEXT,
                    version INTEGER NOT NULL DEFAULT 1,
                    trial_state TEXT NOT NULL DEFAULT 'new'
                )
            """)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(proposals)")}
            if "trial_state" not in columns:
                conn.execute(
                    "ALTER TABLE proposals ADD COLUMN trial_state TEXT NOT NULL DEFAULT 'new'"
                )
            conn.commit()

    def add(self, query_id: str, original_sql: str, proposal: dict) -> str:
        if not isinstance(query_id, str) or not query_id.strip():
            raise ValueError("query_id không hợp lệ")
        ok, _ = ast_check(original_sql)
        if not ok:
            raise ValueError("SQL gốc không qua AST whitelist")
        TrialIndex(proposal)  # kiểm cấu trúc trước khi lưu; chưa gửi DDL
        proposal_id = f"p_{uuid.uuid4().hex}"
        payload = json.dumps(proposal, ensure_ascii=False, allow_nan=False)
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute(
                "INSERT INTO proposals (proposal_id, query_id, original_sql, proposal_json) "
                "VALUES (?, ?, ?, ?)",
                (proposal_id, query_id, original_sql, payload),
            )
            conn.commit()
        return proposal_id

    def get(self, proposal_id: str) -> dict:
        with closing(sqlite3.connect(self.path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM proposals WHERE proposal_id=?", (proposal_id,),
            ).fetchone()
        if row is None:
            raise KeyError("proposal không tồn tại")
        return {
            "proposal_id": row["proposal_id"], "query_id": row["query_id"],
            "original_sql": row["original_sql"], "version": row["version"],
            "trial_state": row["trial_state"],
            "proposal": json.loads(row["proposal_json"]),
            "report": json.loads(row["report_json"]) if row["report_json"] else None,
        }

    def begin_trial(self, proposal_id: str) -> None:
        """Ghi durable intent trước CREATE INDEX; chặn chạy hai lần cùng proposal."""
        with closing(sqlite3.connect(self.path)) as conn:
            result = conn.execute(
                "UPDATE proposals SET trial_state='pending' "
                "WHERE proposal_id=? AND trial_state='new' AND report_json IS NULL",
                (proposal_id,),
            )
            if result.rowcount != 1:
                raise ValueError("proposal không thể bắt đầu trial")
            conn.commit()

    def pending_trials(self) -> list[str]:
        with closing(sqlite3.connect(self.path)) as conn:
            return [row[0] for row in conn.execute(
                "SELECT proposal_id FROM proposals WHERE trial_state='pending'"
            )]

    def save_report(self, proposal_id: str, report: dict) -> dict:
        saved = self.get(proposal_id)
        if (report.get("proposal_id") != proposal_id
                or report.get("query_id") != saved["query_id"]):
            raise ValueError("report không khớp proposal")
        checked = assess_index_report(
            report, expected_index_name=saved["proposal"]["index_name"],
            expected_table=saved["proposal"]["table"],
            original_sql=saved["original_sql"],
        )
        if report.get("failure_reason") == "cleanup_failed":
            checked.update(status="inconclusive", evidence_complete=False,
                           failure_reason="cleanup_failed")
        elif (checked["status"] == "inconclusive"
              and report.get("failure_reason") in {
                  "interrupted", "measurement_error", "ast_rejected",
              }):
            checked["failure_reason"] = report["failure_reason"]
        state = ("pending" if checked["failure_reason"] == "cleanup_failed"
                 else "passed" if checked["status"] == "passed" else "cleaned")
        payload = json.dumps(checked, ensure_ascii=False, allow_nan=False)
        with closing(sqlite3.connect(self.path)) as conn:
            result = conn.execute(
                "UPDATE proposals SET report_json=?, trial_state=? "
                "WHERE proposal_id=? AND trial_state='pending' AND report_json IS NULL",
                (payload, state, proposal_id),
            )
            if result.rowcount != 1:
                raise ValueError("report đã được lưu hoặc proposal không tồn tại")
            conn.commit()
        return checked

    def mark_recovered(self, proposal_id: str) -> None:
        saved = self.get(proposal_id)
        if saved["trial_state"] != "pending":
            raise ValueError("trial không còn pending")
        if saved["report"] is None:
            report = {
                "proposal_id": proposal_id, "query_id": saved["query_id"],
                "candidate_sql_kind": "original", "before": None, "after": None,
                "write_overhead": None, "failure_reason": "interrupted",
            }
            self.save_report(proposal_id, report)
            return
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute(
                "UPDATE proposals SET trial_state='cleaned' "
                "WHERE proposal_id=? AND trial_state='pending'",
                (proposal_id,),
            )
            conn.commit()
