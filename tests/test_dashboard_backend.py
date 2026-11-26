"""
tests/test_dashboard_backend.py
-------------------------------

CHỨC NĂNG : Kiểm tra khôi phục trial khi backend Dashboard khởi động.
PHỤ TRÁCH  : Tình    |    REVIEW: Vũ + Hải
LƯU Ý      : Chỉ dùng store/trial giả, không kết nối MySQL hoặc chạy DDL thật.
"""

import runpy
import sys
from pathlib import Path
from types import ModuleType

import pytest

from dashboard import backend
from security.approval import ApprovalTokens


def test_initialize_backend_recovers_pending_before_returning_store(monkeypatch, tmp_path):
    events = []
    store = object()

    def make_store(path):
        events.append(("open", path))
        return store

    def recover(value):
        events.append(("recover", value))
        return {"p_trial": "dropped"}

    monkeypatch.setattr(backend, "ProposalStore", make_store)
    monkeypatch.setattr(backend, "recover_interrupted_trials", recover)

    assert backend.initialize_backend(tmp_path / "proposals.sqlite3") is store
    assert events == [
        ("open", tmp_path / "proposals.sqlite3"),
        ("recover", store),
    ]


def _approval_saved(**changes):
    saved = {
        "proposal_id": "p_abc", "query_id": "q07", "version": 1,
        "trial_state": "passed",
        "proposal": {"type": "index", "table": "orders",
                     "index_name": "idx_orders_status",
                     "columns": [{"name": "status", "order": "ASC"}]},
        "report": {"proposal_id": "p_abc", "query_id": "q07",
                   "status": "passed", "evidence_complete": True,
                   "candidate_sql_kind": "original", "result_equivalent": True,
                   "failure_reason": None,
                   "db_identity": {"server_uuid": "db-a", "schema": "shopdb",
                                   "host": "127.0.0.1", "port": 3307}},
    }
    saved.update(changes)
    return saved


def test_approval_precheck_returns_canonical_ddl_only_for_owned_trial(monkeypatch):
    monkeypatch.setattr(backend, "current_db_identity",
                        lambda: _approval_saved()["report"]["db_identity"])
    class Trial:
        def __init__(self, proposal, *, proposal_id):
            assert proposal_id == "p_abc"
            assert proposal["index_name"] == "idx_orders_status"
            self.visible_ddl = "ALTER TABLE `orders` ALTER INDEX `idx_orders_status` VISIBLE"

        def _index_state(self):
            return "owned"

    saved = _approval_saved()
    store = type("Store", (), {"get": lambda self, proposal_id: saved})()
    assert backend.approval_precheck(store, "p_abc", trial_factory=Trial) == (
        "ALTER TABLE `orders` ALTER INDEX `idx_orders_status` VISIBLE"
    )


@pytest.mark.parametrize("change", [
    {"trial_state": "cleaned"},
    {"report": None},
    {"report": {**_approval_saved()["report"], "status": "inconclusive"}},
    {"report": {**_approval_saved()["report"], "evidence_complete": False}},
    {"report": {**_approval_saved()["report"], "candidate_sql_kind": "rewritten"}},
    {"report": {**_approval_saved()["report"], "proposal_id": "p_other"}},
    {"proposal": {"type": "rewrite"}},
])
def test_approval_precheck_rejects_ineligible_saved_proposal(change):
    saved = _approval_saved(**change)
    store = type("Store", (), {"get": lambda self, proposal_id: saved})()
    with pytest.raises(ValueError):
        backend.approval_precheck(store, "p_abc", trial_factory=lambda *a, **k: None)


def test_approval_precheck_rejects_missing_or_changed_trial(monkeypatch):
    monkeypatch.setattr(backend, "current_db_identity",
                        lambda: _approval_saved()["report"]["db_identity"])
    saved = _approval_saved()
    store = type("Store", (), {"get": lambda self, proposal_id: saved})()

    class Trial:
        def __init__(self, proposal, *, proposal_id):
            self.visible_ddl = "ALTER TABLE `orders` ALTER INDEX `idx_orders_status` VISIBLE"

        def _index_state(self):
            return "absent"

    with pytest.raises(ValueError):
        backend.approval_precheck(store, "p_abc", trial_factory=Trial)


@pytest.mark.parametrize("identity", [None, {"server_uuid": "db-b", "schema": "shopdb",
                                            "host": "127.0.0.1", "port": 3307}])
def test_approval_precheck_rejects_missing_or_other_database(monkeypatch, identity):
    monkeypatch.setattr(backend, "current_db_identity",
                        lambda: _approval_saved()["report"]["db_identity"])
    saved = _approval_saved()
    saved["report"]["db_identity"] = identity
    store = type("Store", (), {"get": lambda self, proposal_id: saved})()
    with pytest.raises(ValueError, match="DB"):
        backend.approval_precheck(store, "p_abc", trial_factory=lambda *a, **k: None)


def test_issue_approval_token_binds_saved_proposal_and_ddl(monkeypatch, tmp_path):
    saved = _approval_saved()
    store = type("Store", (), {"get": lambda self, proposal_id: saved})()
    ddl = "ALTER TABLE `orders` ALTER INDEX `idx_orders_status` VISIBLE"
    monkeypatch.setattr(backend, "current_db_identity",
                        lambda: saved["report"]["db_identity"])
    monkeypatch.setattr(backend.Config, "APPROVAL_SECRET", "test-only-secret")

    class Trial:
        def __init__(self, proposal, *, proposal_id):
            self.visible_ddl = ddl

        def _index_state(self):
            return "owned"

    token_path = tmp_path / "tokens.sqlite3"
    token = backend.issue_approval_token(
        store, "p_abc", token_path=token_path, trial_factory=Trial,
    )
    tokens = ApprovalTokens(token_path, secret="test-only-secret")
    assert not tokens.verify_token(token, "p_abc", 2, ddl)
    assert not tokens.verify_token(token, "p_abc", 1, ddl + " ")
    assert tokens.verify_token(token, "p_abc", 1, ddl)


def test_issue_approval_token_refuses_report_from_other_db(monkeypatch, tmp_path):
    saved = _approval_saved()
    saved["report"]["db_identity"]["server_uuid"] = "other-db"
    store = type("Store", (), {"get": lambda self, proposal_id: saved})()
    monkeypatch.setattr(backend, "current_db_identity",
                        lambda: _approval_saved()["report"]["db_identity"])
    monkeypatch.setattr(backend.Config, "APPROVAL_SECRET", "test-only-secret")
    token_path = tmp_path / "tokens.sqlite3"
    with pytest.raises(ValueError, match="DB"):
        backend.issue_approval_token(store, "p_abc", token_path=token_path)
    assert not token_path.exists()


def test_initialize_backend_refuses_failed_recovery(monkeypatch, tmp_path):
    monkeypatch.setattr(backend, "ProposalStore", lambda path: object())
    monkeypatch.setattr(
        backend, "recover_interrupted_trials",
        lambda store: {"p_trial": "recovery_failed"},
    )

    with pytest.raises(RuntimeError, match="p_trial"):
        backend.initialize_backend(tmp_path / "proposals.sqlite3")


def test_dashboard_starts_recovery_before_rendering(monkeypatch):
    events = []
    store = object()
    fake_streamlit = ModuleType("streamlit")
    fake_streamlit.cache_resource = lambda function: function
    fake_streamlit.error = lambda message: events.append(("error", message))
    fake_streamlit.stop = lambda: events.append(("stop",))
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)
    monkeypatch.setattr(
        backend, "initialize_backend", lambda: events.append(("recover",)) or store,
    )

    app_globals = runpy.run_path(str(Path(backend.__file__).with_name("app.py")))

    assert events == [("recover",)]
    assert app_globals["proposal_store"] is store


def test_dashboard_stops_when_recovery_fails(monkeypatch):
    events = []
    fake_streamlit = ModuleType("streamlit")
    fake_streamlit.cache_resource = lambda function: function
    fake_streamlit.error = lambda message: events.append(("error", message))

    def stop():
        events.append(("stop",))
        raise RuntimeError("stopped")

    def fail_recovery():
        raise RuntimeError("pending trial")

    fake_streamlit.stop = stop
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)
    monkeypatch.setattr(backend, "initialize_backend", fail_recovery)

    with pytest.raises(RuntimeError, match="stopped"):
        runpy.run_path(str(Path(backend.__file__).with_name("app.py")))

    assert events[0][0] == "error"
    assert events[1] == ("stop",)


@pytest.mark.asyncio
async def test_validation_uses_the_store_recovered_at_startup(monkeypatch, tmp_path):
    events = []
    store_path = tmp_path / "proposals.sqlite3"
    csv_dir = tmp_path / "csv"
    monkeypatch.setattr(
        backend, "recover_interrupted_trials",
        lambda store: events.append(("recover", store.path)) or {},
    )
    store = backend.initialize_backend(store_path)

    async def fake_validate(actual_store, proposal_id, *, write_csv_dir):
        events.append(("validate", actual_store.path, proposal_id, write_csv_dir))
        assert actual_store is store
        return {"status": "inconclusive"}

    monkeypatch.setattr(backend, "validate_saved_index", fake_validate, raising=False)
    report = await backend.validate_proposal(
        store, "p_trial", write_csv_dir=csv_dir,
    )

    assert report == {"status": "inconclusive"}
    assert events == [
        ("recover", store_path),
        ("validate", store_path, "p_trial", csv_dir),
    ]
