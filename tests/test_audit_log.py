"""Kiểm tra nhật ký Tool 6 chỉ ghi thêm và không chứa token."""

import sqlite3

from mcp_server.store.audit_log import AuditLog


def test_audit_log_persists_attempt_and_result_without_token(tmp_path):
    path = tmp_path / "audit.sqlite3"
    log = AuditLog(path)
    first = log.append(proposal_id="p_abc", ddl_sha256=None,
                       result="rejected", approver="dashboard-user",
                       source="dashboard", reason="TOKEN_INVALID")
    second = AuditLog(path).append(proposal_id="p_abc", ddl_sha256="a" * 64,
                                   result="applied", approver="dashboard-user",
                                   source="dashboard", reason=None)

    with sqlite3.connect(path) as conn:
        rows = conn.execute(
            "SELECT audit_id, proposal_id, ddl_sha256, result, approver, source, reason "
            "FROM audit_log ORDER BY audit_id"
        ).fetchall()
        columns = [row[1] for row in conn.execute("PRAGMA table_info(audit_log)")]

    assert [row[0] for row in rows] == [first, second]
    assert rows[0][1:] == ("p_abc", None, "rejected", "dashboard-user",
                           "dashboard", "TOKEN_INVALID")
    assert rows[1][2:4] == ("a" * 64, "applied")
    assert "token" not in " ".join(columns)
