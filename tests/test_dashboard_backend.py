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
