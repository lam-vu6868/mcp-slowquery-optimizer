"""
tests/test_dashboard_backend.py
-------------------------------

CHỨC NĂNG : Kiểm tra khôi phục trial khi backend Dashboard khởi động.
PHỤ TRÁCH  : Tình    |    REVIEW: Vũ + Hải
LƯU Ý      : Chỉ dùng store/trial giả, không kết nối MySQL hoặc chạy DDL thật.
"""

import os
import runpy
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from dashboard import backend
from security.approval import ApprovalTokens


def _widget(widgets, label):
    return next(widget for widget in widgets if widget.label == label)


def test_dashboard_store_env_keeps_lab_token_and_audit_separate(tmp_path):
    lab_store = tmp_path / "lab_proposals.sqlite3"
    command = (
        "from dashboard.backend import DEFAULT_STORE_PATH, DEFAULT_TOKEN_PATH, "
        "DEFAULT_AUDIT_PATH; print(DEFAULT_STORE_PATH, DEFAULT_TOKEN_PATH, "
        "DEFAULT_AUDIT_PATH, sep='\\n')"
    )
    result = subprocess.run(
        [sys.executable, "-c", command], cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "DASHBOARD_STORE_PATH": str(lab_store)},
        capture_output=True, text=True, check=True,
    )
    assert result.stdout.splitlines() == [
        str(lab_store), str(tmp_path / "approval_tokens.sqlite3"),
        str(tmp_path / "audit.sqlite3"),
    ]


def test_initialize_backend_recovers_pending_before_returning_store(monkeypatch, tmp_path):
    events = []
    store = object()

    def make_store(path):
        events.append(("open", path))
        return store

    def recover(value):
        events.append(("recover", value))
        return {"p_trial": "dropped"}

    def expire(value):
        events.append(("expire", value))
        return {"p_old": "dropped"}

    monkeypatch.setattr(backend, "ProposalStore", make_store)
    monkeypatch.setattr(backend, "recover_interrupted_trials", recover)
    monkeypatch.setattr(backend, "expire_waiting_trials", expire)

    assert backend.initialize_backend(tmp_path / "proposals.sqlite3") is store
    assert events == [
        ("open", tmp_path / "proposals.sqlite3"),
        ("recover", store),
        ("expire", store),
    ]


def _approval_saved(**changes):
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


def test_approval_precheck_rejects_expired_trial_before_token_or_db():
    saved = _approval_saved(review_expires_at=1)
    store = type("Store", (), {"get": lambda self, proposal_id: saved})()
    with pytest.raises(ValueError, match="hết hạn"):
        backend.approval_precheck(store, "p_abc",
                                  trial_factory=lambda *a, **k: pytest.fail("no DB"))


def test_approval_precheck_rejects_legacy_trial_without_deadline():
    saved = _approval_saved(review_expires_at=None)
    store = type("Store", (), {"get": lambda self, proposal_id: saved})()
    with pytest.raises(ValueError, match="hết hạn"):
        backend.approval_precheck(store, "p_abc",
                                  trial_factory=lambda *a, **k: pytest.fail("no DB"))


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


@pytest.mark.asyncio
async def test_local_dashboard_calls_private_tool6_with_os_account(monkeypatch, tmp_path):
    events = []
    store = object()
    token_path = tmp_path / "tokens.sqlite3"
    audit_path = tmp_path / "audit.sqlite3"
    monkeypatch.setattr(backend.getpass, "getuser", lambda: "local-operator", raising=False)
    monkeypatch.setattr(backend.Config, "APPROVAL_SECRET", "test-only-secret")
    monkeypatch.setattr(backend, "issue_approval_token",
                        lambda actual_store, proposal_id, *, token_path: (
                            events.append(("issue", actual_store, proposal_id, token_path))
                            or "test-token"))

    class FakeApplier:
        def __init__(self, actual_store, tokens, audit, *, approver):
            assert actual_store is store
            assert approver == "local-operator"
            assert tokens.path == token_path
            assert audit.path == audit_path

        def apply_optimization(self, proposal_id, approval_token):
            events.append(("apply", proposal_id, approval_token))
            return {"applied": True, "audit_id": "a_000001"}

    monkeypatch.setattr(backend, "OptimizationApplier", FakeApplier, raising=False)
    result = await backend.apply_from_dashboard(
        store, "p_abc", token_path=token_path, audit_path=audit_path,
    )
    assert result == {"applied": True, "audit_id": "a_000001"}
    assert events == [("issue", store, "p_abc", token_path),
                      ("apply", "p_abc", "test-token")]


@pytest.mark.asyncio
async def test_local_dashboard_refuses_missing_os_account(monkeypatch, tmp_path):
    monkeypatch.setattr(backend.getpass, "getuser", lambda: "", raising=False)
    monkeypatch.setattr(backend, "issue_approval_token",
                        lambda *args, **kwargs: pytest.fail("token must not be issued"))
    with pytest.raises(ValueError, match="tài khoản"):
        await backend.apply_from_dashboard(object(), "p_abc",
                                           token_path=tmp_path / "tokens.sqlite3",
                                           audit_path=tmp_path / "audit.sqlite3")


@pytest.mark.asyncio
async def test_local_dashboard_hides_tool_error_and_token(monkeypatch, tmp_path):
    monkeypatch.setattr(backend.getpass, "getuser", lambda: "local-operator")
    monkeypatch.setattr(backend.Config, "APPROVAL_SECRET", "test-only-secret")
    monkeypatch.setattr(backend, "issue_approval_token",
                        lambda *args, **kwargs: "private-token")
    monkeypatch.setattr(backend, "OptimizationApplier", lambda *args, **kwargs: object())

    class FailingRegistry:
        async def call_tool(self, name, arguments):
            assert arguments["approval_token"] == "private-token"
            return SimpleNamespace(is_error=True, content=[])

    monkeypatch.setattr(backend, "make_dashboard_mcp",
                        lambda applier: FailingRegistry())
    with pytest.raises(RuntimeError, match="Tool 6") as exc:
        await backend.apply_from_dashboard(
            object(), "p_abc", token_path=tmp_path / "tokens.sqlite3",
            audit_path=tmp_path / "audit.sqlite3",
        )
    assert "private-token" not in str(exc.value)


def test_streamlit_dashboard_is_bound_to_loopback():
    path = Path(backend.__file__).resolve().parents[1] / ".streamlit" / "config.toml"
    with path.open("rb") as config_file:
        settings = tomllib.load(config_file)
    assert settings["server"]["address"] == "127.0.0.1"


def test_initialize_backend_refuses_failed_recovery(monkeypatch, tmp_path):
    monkeypatch.setattr(backend, "ProposalStore", lambda path: object())
    monkeypatch.setattr(
        backend, "recover_interrupted_trials",
        lambda store: {"p_trial": "recovery_failed"},
    )

    with pytest.raises(RuntimeError, match="p_trial"):
        backend.initialize_backend(tmp_path / "proposals.sqlite3")


def test_initialize_backend_refuses_failed_expiry_cleanup(monkeypatch, tmp_path):
    monkeypatch.setattr(backend, "ProposalStore", lambda path: object())
    monkeypatch.setattr(backend, "recover_interrupted_trials", lambda store: {})
    monkeypatch.setattr(backend, "expire_waiting_trials",
                        lambda store: {"p_old": "cleanup_failed"})
    with pytest.raises(RuntimeError, match="p_old"):
        backend.initialize_backend(tmp_path / "proposals.sqlite3")


def test_reject_from_dashboard_calls_guarded_cleanup(monkeypatch):
    events = []
    store = object()
    monkeypatch.setattr(backend, "reject_saved_index",
                        lambda actual, proposal_id: events.append((actual, proposal_id)) or "dropped")
    assert backend.reject_from_dashboard(store, "p_abc") == "dropped"
    assert events == [(store, "p_abc")]


def test_dashboard_starts_recovery_before_rendering(monkeypatch):
    events = []
    store = object()
    fake_streamlit = ModuleType("streamlit")
    fake_streamlit.cache_resource = lambda function: function
    fake_streamlit.session_state = {}
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


@pytest.mark.asyncio
async def test_dashboard_validation_refuses_main_db_before_any_ddl(monkeypatch, tmp_path):
    monkeypatch.setattr(backend.Config, "DB_HOST", "127.0.0.1")
    monkeypatch.setattr(backend.Config, "DB_PORT", 3307)
    monkeypatch.setattr(backend.Config, "DB_NAME", "shopdb")
    store = type("Store", (), {"get": lambda self, proposal_id: pytest.fail("no store")})()
    with pytest.raises(ValueError, match="lab 3309"):
        await backend.validate_from_dashboard(
            store, "p_abc", write_csv_dir=tmp_path,
        )


@pytest.mark.asyncio
async def test_dashboard_validation_checks_csv_and_lab_marker_before_call(
    monkeypatch, tmp_path,
):
    from contextlib import contextmanager

    monkeypatch.setattr(backend.Config, "DB_HOST", "127.0.0.1")
    monkeypatch.setattr(backend.Config, "DB_PORT", 3309)
    monkeypatch.setattr(backend.Config, "DB_NAME", "shopdb")
    events = []
    marker = {"value": "wrong-lab"}
    saved = _approval_saved(trial_state="new")
    store = type("Store", (), {"get": lambda self, proposal_id: saved})()

    class Conn:
        def cursor(self):
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql):
            events.append(("marker_query", sql))

        def fetchone(self):
            return {"marker": marker["value"]}

    @contextmanager
    def fake_conn():
        yield Conn()

    async def fake_validate(actual, proposal_id, *, write_csv_dir):
        events.append(("validate", actual, proposal_id, write_csv_dir))
        return {"status": "passed"}

    monkeypatch.setattr(backend, "get_conn", fake_conn, raising=False)
    monkeypatch.setattr(backend, "validate_proposal", fake_validate)
    with pytest.raises(ValueError, match="CSV"):
        await backend.validate_from_dashboard(store, "p_abc", write_csv_dir=tmp_path)
    assert events == []

    (tmp_path / "orders.csv").write_text("id\n", encoding="utf-8")
    with pytest.raises(ValueError, match="marker"):
        await backend.validate_from_dashboard(
            store, "p_abc", write_csv_dir=tmp_path,
        )
    assert not any(item[0] == "validate" for item in events)

    marker["value"] = "mcp-validation-lab-v1"
    assert await backend.validate_from_dashboard(
        store, "p_abc", write_csv_dir=tmp_path,
    ) == {"status": "passed"}
    assert events[-1] == ("validate", store, "p_abc", tmp_path)


def test_proposals_page_requires_confirmation_before_actions(monkeypatch):
    from streamlit.testing.v1 import AppTest

    saved = _approval_saved()
    saved["original_sql"] = "SELECT id FROM orders"
    store = type("Store", (), {"recent_proposals": lambda self: [saved]})()
    events = []

    async def fake_apply(actual, proposal_id):
        events.append(("approve", actual, proposal_id))

    monkeypatch.setattr(backend, "apply_from_dashboard", fake_apply)
    monkeypatch.setattr(backend, "reject_from_dashboard",
                        lambda actual, proposal_id: events.append(
                            ("reject", actual, proposal_id)))
    page = Path(backend.__file__).parent / "pages" / "2_proposals.py"
    at = AppTest.from_file(str(page))
    at.session_state["proposal_store"] = store
    at.run()
    assert not at.exception
    assert _widget(at.button, "Approve").disabled
    assert _widget(at.button, "Reject").disabled
    assert events == []

    _widget(at.checkbox, "Tôi xác nhận thao tác trên MySQL").set_value(True).run()
    assert not _widget(at.button, "Approve").disabled
    assert not _widget(at.button, "Reject").disabled
    _widget(at.button, "Approve").click().run()
    assert events == [("approve", store, "p_abc")]

    _widget(at.button, "Reject").click().run()
    assert events[-1] == ("reject", store, "p_abc")


@pytest.mark.parametrize("changes,button_count", [
    ({"proposal": {"type": "rewrite"}}, 0),
    ({"review_expires_at": 1}, 2),
])
def test_proposals_page_keeps_approve_unavailable_for_rewrite_or_expired(
    changes, button_count,
):
    from streamlit.testing.v1 import AppTest

    saved = _approval_saved(**changes)
    saved["original_sql"] = "SELECT id FROM orders"
    store = type("Store", (), {"recent_proposals": lambda self: [saved]})()
    at = AppTest.from_file(str(Path(backend.__file__).parent / "pages" / "2_proposals.py"))
    at.session_state["proposal_store"] = store
    at.run()
    assert not at.exception
    action_buttons = [button for button in at.button
                      if button.label in {"Approve", "Reject"}]
    assert len(action_buttons) == button_count
    if button_count:
        _widget(at.checkbox, "Tôi xác nhận thao tác trên MySQL").set_value(True).run()
        assert _widget(at.button, "Approve").disabled


def test_proposals_page_runs_validation_only_after_confirmation(monkeypatch):
    from streamlit.testing.v1 import AppTest

    saved = _approval_saved(trial_state="new", report=None, review_expires_at=None)
    saved["original_sql"] = "SELECT id FROM orders"
    store = type("Store", (), {"recent_proposals": lambda self: [saved]})()
    events = []

    async def fake_validate(actual, proposal_id, *, write_csv_dir):
        events.append((actual, proposal_id, write_csv_dir))
        return {"status": "passed"}

    monkeypatch.setattr(backend, "validate_from_dashboard", fake_validate)
    at = AppTest.from_file(str(Path(backend.__file__).parent / "pages" / "2_proposals.py"))
    at.session_state["proposal_store"] = store
    at.run()
    assert not at.exception
    assert _widget(at.button, "Chạy Validation").disabled
    assert events == []

    _widget(at.text_input, "Thư mục CSV cho write lab").set_value("C:/lab/data").run()
    assert _widget(at.button, "Chạy Validation").disabled
    _widget(at.checkbox, "Tôi xác nhận chạy Validation trên lab").set_value(True).run()
    assert not _widget(at.button, "Chạy Validation").disabled
    _widget(at.button, "Chạy Validation").click().run()
    assert events == [(store, "p_abc", Path("C:/lab/data"))]


def test_proposals_page_refreshes_state_after_reject(monkeypatch):
    from streamlit.testing.v1 import AppTest

    saved = _approval_saved()
    saved["original_sql"] = "SELECT id FROM orders"
    store = type("Store", (), {"recent_proposals": lambda self: [saved]})()

    def fake_reject(actual, proposal_id):
        assert actual is store and proposal_id == "p_abc"
        saved["trial_state"] = "cleaned"
        return "dropped"

    monkeypatch.setattr(backend, "reject_from_dashboard", fake_reject)
    at = AppTest.from_file(str(Path(backend.__file__).parent / "pages" / "2_proposals.py"))
    at.session_state["proposal_store"] = store
    at.run()
    _widget(at.checkbox, "Tôi xác nhận thao tác trên MySQL").set_value(True).run()
    _widget(at.button, "Reject").click().run()
    assert not at.exception
    assert not any(button.label in {"Approve", "Reject"} for button in at.button)
    assert at.success[0].value == "Đã dọn index thử."
