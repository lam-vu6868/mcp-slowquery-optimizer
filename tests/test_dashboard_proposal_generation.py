"""Kiểm đường tạo đề xuất từ Dashboard bằng LLM/MCP giả, không gọi API hay MySQL."""

from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from dashboard import backend
from mcp_server.store.proposals import ProposalStore


@pytest.mark.asyncio
async def test_generate_proposals_rejects_unsafe_sql_before_llm(monkeypatch, tmp_path):
    store = ProposalStore(tmp_path / "proposals.sqlite3")
    monkeypatch.setattr(backend, "create_groq_client", lambda: pytest.fail("LLM called"),
                        raising=False)

    with pytest.raises(ValueError, match="SQL"):
        await backend.generate_proposals_from_dashboard(store, "q07", "DROP TABLE orders")
    assert store.recent_proposals() == []


@pytest.mark.asyncio
async def test_generate_proposals_saves_index_and_display_only_rewrite(monkeypatch, tmp_path):
    store = ProposalStore(tmp_path / "proposals.sqlite3")
    closed = []
    client = SimpleNamespace(close=lambda: None)

    async def close():
        closed.append(True)

    client.close = close

    @asynccontextmanager
    async def fake_stdio(params):
        assert params.args == ["-m", "mcp_server.server"]
        yield (object(), object())

    class FakeSession:
        def __init__(self, *_):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def initialize(self):
            pass

    index = {"type": "index", "table": "orders", "index_name": "idx_orders_status",
             "columns": [{"name": "status", "order": "ASC"}],
             "rationale": "Lọc trạng thái", "target_query_ids": ["q07"]}
    rewrite = {"type": "rewrite", "original_query_id": "q07",
               "rewritten_sql": "SELECT order_id FROM orders WHERE status='paid'",
               "rationale": "Giảm cột trả về"}

    async def fake_analyze(query_id, sql, *, llm_client, mcp_client):
        assert (query_id, sql, llm_client, mcp_client) == (
            "q07", "SELECT order_id FROM orders", client, session[0],
        )
        return {"query_id": query_id, "proposals": [index, rewrite]}

    session = []
    original_enter = FakeSession.__aenter__

    async def enter(self):
        value = await original_enter(self)
        session.append(value)
        return value

    FakeSession.__aenter__ = enter
    monkeypatch.setattr(backend, "create_groq_client", lambda: client, raising=False)
    monkeypatch.setattr(backend, "stdio_client", fake_stdio, raising=False)
    monkeypatch.setattr(backend, "ClientSession", FakeSession, raising=False)
    monkeypatch.setattr(backend, "analyze_query", fake_analyze, raising=False)

    ids = await backend.generate_proposals_from_dashboard(
        store, "q07", "SELECT order_id FROM orders",
    )
    assert len(ids) == 2
    assert {store.get(proposal_id)["proposal"]["type"] for proposal_id in ids} == {
        "index", "rewrite",
    }
    assert closed == [True]


@pytest.mark.asyncio
async def test_generate_proposals_does_not_save_parse_failure(monkeypatch, tmp_path):
    store = ProposalStore(tmp_path / "proposals.sqlite3")

    @asynccontextmanager
    async def fake_stdio(_):
        yield (object(), object())

    class FakeSession:
        def __init__(self, *_):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def initialize(self):
            pass

    async def close():
        pass

    async def fake_analyze(*_args, **_kwargs):
        return {"query_id": "q07", "status": "parse_failed"}

    monkeypatch.setattr(backend, "create_groq_client", lambda: SimpleNamespace(close=close),
                        raising=False)
    monkeypatch.setattr(backend, "stdio_client", fake_stdio, raising=False)
    monkeypatch.setattr(backend, "ClientSession", FakeSession, raising=False)
    monkeypatch.setattr(backend, "analyze_query", fake_analyze, raising=False)

    with pytest.raises(ValueError, match="LLM"):
        await backend.generate_proposals_from_dashboard(
            store, "q07", "SELECT order_id FROM orders",
        )
    assert store.recent_proposals() == []


def test_rewrite_store_rejects_unsafe_sql_and_never_gets_trial(tmp_path):
    store = ProposalStore(tmp_path / "proposals.sqlite3")
    rewrite = {"type": "rewrite", "original_query_id": "q07",
               "rewritten_sql": "SELECT order_id FROM orders", "rationale": "Ít cột"}
    proposal_id = store.add("q07", "SELECT * FROM orders", rewrite)
    assert store.get(proposal_id)["trial_state"] == "new"
    with pytest.raises(ValueError, match="SQL"):
        store.add("q07", "SELECT * FROM orders", {
            **rewrite, "rewritten_sql": "DROP TABLE orders",
        })


def test_generated_batch_is_all_or_nothing(tmp_path):
    store = ProposalStore(tmp_path / "proposals.sqlite3")
    index = {"type": "index", "table": "orders", "index_name": "idx_orders_status",
             "columns": [{"name": "status", "order": "ASC"}]}
    unsafe_rewrite = {"type": "rewrite", "original_query_id": "q07",
                      "rewritten_sql": "DROP TABLE orders"}
    with pytest.raises(ValueError, match="SQL"):
        store.add_many("q07", "SELECT * FROM orders", [index, unsafe_rewrite])
    assert store.recent_proposals() == []


def test_proposals_page_can_request_generation_when_store_is_empty(monkeypatch):
    saved = []
    store = type("Store", (), {"recent_proposals": lambda self: saved})()

    async def generate(actual, query_id, sql):
        assert (actual, query_id, sql) == (store, "q07", "SELECT 1")
        saved.append({"proposal_id": "p_test", "query_id": "q07",
                      "original_sql": sql, "proposal": {"type": "rewrite"},
                      "trial_state": "new", "report": None})
        return ["p_test"]

    monkeypatch.setattr(backend, "generate_proposals_from_dashboard", generate,
                        raising=False)
    page = Path(backend.__file__).parent / "pages" / "2_llm_de_xuat.py"
    at = AppTest.from_file(str(page))
    at.session_state["proposal_store"] = store
    at.run()
    assert not at.exception
    assert at.button[0].disabled
    at.text_input[0].set_value("q07").run()
    at.text_area[0].set_value("SELECT 1").run()
    assert at.button[0].disabled
    at.checkbox[0].set_value(True).run()
    at.button[0].click().run()
    assert not at.exception
    assert at.success[0].value == "Đã lưu 1 đề xuất."
    assert len(saved) == 1
