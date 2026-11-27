"""Kiểm tra lõi Tool 6 bằng DB giả; không thực hiện DDL thật."""

import sqlite3
import time
from contextlib import contextmanager

import pytest

from mcp_server.store.audit_log import AuditLog
from mcp_server.tools import apply as apply_module
from mcp_server.tools.apply import OptimizationApplier, TrialIndex
from security.approval import ApprovalTokens

DDL = "ALTER TABLE `orders` ALTER INDEX `idx_orders_status` VISIBLE"
IDENTITY = {"server_uuid": "db-a", "schema": "shopdb",
            "host": "127.0.0.1", "port": 3307}


def _setup(tmp_path):
    saved = {
        "proposal_id": "p_abc", "query_id": "q07", "version": 1,
        "trial_state": "passed",
        "review_expires_at": int(time.time()) + 86400,
        "proposal": {"type": "index", "table": "orders",
                     "index_name": "idx_orders_status",
                     "columns": [{"name": "status", "order": "ASC"}]},
        "report": {"proposal_id": "p_abc", "query_id": "q07",
                   "status": "passed", "evidence_complete": True,
                   "candidate_sql_kind": "original", "result_equivalent": True,
                   "failure_reason": None, "db_identity": IDENTITY,
                   "write_overhead": {"index_size_bytes": 1024,
                                      "index_size_source": "innodb_index_stats_pages"}},
    }
    class Store:
        def get(self, proposal_id):
            return saved

        def mark_applied(self, proposal_id):
            saved["trial_state"] = "applied"

    store = Store()
    tokens = ApprovalTokens(tmp_path / "tokens.sqlite3", secret="test-secret")
    audit = AuditLog(tmp_path / "audit.sqlite3")
    state = {"visible": False, "ddl_calls": []}

    class Trial:
        def __init__(self, proposal, *, proposal_id):
            self.visible_ddl = DDL
            self.drop_ddl = "DROP INDEX `idx_orders_status` ON `orders`"

        def _index_state(self):
            return "owned" if not state["visible"] else "visible"

        def is_visible(self):
            return state["visible"]

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql):
            if sql == DDL:
                state["ddl_calls"].append(sql)
                state["visible"] = True

    class Connection:
        def cursor(self):
            return Cursor()

    @contextmanager
    def admin_conn():
        yield Connection()

    applier = OptimizationApplier(
        store, tokens, audit, approver="tester", trial_factory=Trial,
        identity_reader=lambda: IDENTITY, admin_conn=admin_conn,
    )
    return saved, tokens, audit, state, applier


def test_tool6_applies_exact_approved_ddl_once_and_audits(tmp_path):
    saved, tokens, audit, state, applier = _setup(tmp_path)
    token = tokens.issue_token("p_abc", 1, DDL)
    result = applier.apply_optimization("p_abc", token)
    assert result["applied"] is True
    assert result["index_visible"] is True
    assert result["ddl"] == DDL
    assert result["index_size_bytes"] == 1024
    assert result["audit_id"].startswith("a_")
    assert state["ddl_calls"] == [DDL]
    assert saved["trial_state"] == "applied"
    assert not tokens.verify_token(token, "p_abc", 1, DDL)
    with sqlite3.connect(audit.path) as conn:
        rows = conn.execute("SELECT result, reason FROM audit_log ORDER BY audit_id").fetchall()
    assert rows == [("attempted", None), ("applied", None)]


def test_tool6_rejects_wrong_db_before_token_or_ddl(tmp_path):
    saved, tokens, audit, state, applier = _setup(tmp_path)
    saved["report"]["db_identity"] = {**IDENTITY, "server_uuid": "db-b"}
    token = tokens.issue_token("p_abc", 1, DDL)
    with pytest.raises(ValueError, match="DB"):
        applier.apply_optimization("p_abc", token)
    assert state["ddl_calls"] == []
    assert tokens.verify_token(token, "p_abc", 1, DDL)
    with sqlite3.connect(audit.path) as conn:
        rows = conn.execute("SELECT result, reason FROM audit_log ORDER BY audit_id").fetchall()
    assert rows == [("attempted", None), ("rejected", "VALIDATION_FAILED")]


def test_tool6_rejects_missing_index_size_before_ddl(tmp_path):
    saved, tokens, _, state, applier = _setup(tmp_path)
    saved["report"]["write_overhead"] = None
    token = tokens.issue_token("p_abc", 1, DDL)
    with pytest.raises(ValueError, match="số đo"):
        applier.apply_optimization("p_abc", token)
    assert state["ddl_calls"] == []
    assert tokens.verify_token(token, "p_abc", 1, DDL)


def test_tool6_rejects_invalid_token_and_audits(tmp_path):
    _, _, audit, state, applier = _setup(tmp_path)
    with pytest.raises(ValueError, match="TOKEN_INVALID"):
        applier.apply_optimization("p_abc", "wrong-token")
    assert state["ddl_calls"] == []
    with sqlite3.connect(audit.path) as conn:
        rows = conn.execute("SELECT result, reason FROM audit_log ORDER BY audit_id").fetchall()
    assert rows == [("attempted", None), ("rejected", "TOKEN_INVALID")]


def test_tool6_audits_unknown_proposal(tmp_path):
    _, _, audit, state, applier = _setup(tmp_path)

    class EmptyStore:
        def get(self, proposal_id):
            raise KeyError(proposal_id)

    applier.store = EmptyStore()
    with pytest.raises(KeyError):
        applier.apply_optimization("p_missing", "wrong-token")
    assert state["ddl_calls"] == []
    with sqlite3.connect(audit.path) as conn:
        rows = conn.execute("SELECT result, reason FROM audit_log ORDER BY audit_id").fetchall()
    assert rows == [("attempted", None), ("rejected", "NOT_FOUND")]


def test_tool6_records_ddl_failure_and_does_not_reuse_token(tmp_path):
    _, tokens, audit, state, applier = _setup(tmp_path)
    token = tokens.issue_token("p_abc", 1, DDL)

    @contextmanager
    def broken_admin():
        raise OSError("DDL failed")
        yield

    applier.admin_conn = broken_admin
    with pytest.raises(OSError, match="DDL failed"):
        applier.apply_optimization("p_abc", token)
    assert state["ddl_calls"] == []
    assert not tokens.verify_token(token, "p_abc", 1, DDL)
    with sqlite3.connect(audit.path) as conn:
        rows = conn.execute("SELECT result, reason FROM audit_log ORDER BY audit_id").fetchall()
    assert rows == [("attempted", None), ("failed", "APPLY_FAILED")]


def test_tool6_marks_post_ddl_verification_as_uncertain(tmp_path):
    saved, tokens, audit, state, applier = _setup(tmp_path)
    token = tokens.issue_token("p_abc", 1, DDL)
    original_trial = applier.trial_factory

    class UnverifiedTrial(original_trial):
        def is_visible(self):
            return False

    applier.trial_factory = UnverifiedTrial
    with pytest.raises(RuntimeError, match="VISIBLE"):
        applier.apply_optimization("p_abc", token)
    assert state["ddl_calls"] == [DDL]
    assert saved["trial_state"] == "passed"
    with sqlite3.connect(audit.path) as conn:
        rows = conn.execute("SELECT result, reason FROM audit_log ORDER BY audit_id").fetchall()
    assert rows == [("attempted", None), ("uncertain", "APPLY_UNVERIFIED")]


def test_tool6_does_not_run_ddl_when_audit_is_unavailable(tmp_path):
    _, tokens, _, state, applier = _setup(tmp_path)
    token = tokens.issue_token("p_abc", 1, DDL)

    class BrokenAudit:
        def append(self, **kwargs):
            raise OSError("audit unavailable")

    applier.audit = BrokenAudit()
    with pytest.raises(OSError, match="audit unavailable"):
        applier.apply_optimization("p_abc", token)
    assert state["ddl_calls"] == []
    assert tokens.verify_token(token, "p_abc", 1, DDL)


def test_visible_index_check_requires_original_marker_and_columns(monkeypatch):
    rows = [{"COLUMN_NAME": "status", "COLLATION": "A",
             "INDEX_COMMENT": "mcp_trial:p_abc", "IS_VISIBLE": "YES"}]

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql, params):
            assert params[-1] == "idx_orders_status"

        def fetchall(self):
            return rows

    class Connection:
        def cursor(self):
            return Cursor()

    @contextmanager
    def readonly():
        yield Connection()

    monkeypatch.setattr(apply_module, "get_conn", readonly)
    trial = TrialIndex({"type": "index", "table": "orders",
                        "index_name": "idx_orders_status",
                        "columns": [{"name": "status", "order": "ASC"}]},
                       proposal_id="p_abc")
    assert trial.is_visible()
    rows[0]["INDEX_COMMENT"] = "other"
    assert not trial.is_visible()
